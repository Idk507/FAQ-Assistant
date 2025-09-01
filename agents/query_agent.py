import json
import logging
from typing import Dict, List, Any, Optional
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from duckduckgo_search import DDGS
import re
from datetime import datetime, timedelta
from config.azure_config import AZURE_OPENAI_CONFIG
from utils.memory_storage import RegulatoryKnowledgeBase

logger = logging.getLogger(__name__)

class QueryAgent:
    """
    Agent responsible for answering user queries with conversational memory
    and real-time search capabilities using DDGS.
    """

    def __init__(self, knowledge_base: RegulatoryKnowledgeBase):
        self.knowledge_base = knowledge_base

        # Initialize Azure OpenAI LLM
        self.llm = AzureChatOpenAI(
            azure_endpoint=AZURE_OPENAI_CONFIG["endpoint"],
            azure_deployment=AZURE_OPENAI_CONFIG["gpt_deployment"],
            api_version=AZURE_OPENAI_CONFIG["api_version"],
            api_key=AZURE_OPENAI_CONFIG["api_key"],
            temperature=0.2,  # Slightly creative for conversational responses
            max_tokens=1500
        )

        # Initialize embeddings for semantic search
        self.embeddings = AzureOpenAIEmbeddings(
            azure_endpoint=AZURE_OPENAI_CONFIG["endpoint"],
            azure_deployment=AZURE_OPENAI_CONFIG["embedding_deployment"],
            api_version=AZURE_OPENAI_CONFIG["api_version"],
            api_key=AZURE_OPENAI_CONFIG["api_key"]
        )

        # Initialize conversation memory
        from langchain.memory import ConversationBufferWindowMemory
        self.memory = ConversationBufferWindowMemory(
            return_messages=True,
            memory_key="chat_history",
            max_token_limit=2000,
            k=10  # Keep last 10 interactions
        )

        # Initialize DuckDuckGo search
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        self.ddgs = DDGS()

        # Define the query response prompt
        self.query_prompt = PromptTemplate(
            input_variables=["query", "context", "chat_history", "search_results"],
            template="""
You are a knowledgeable banking regulatory assistant. Answer customer queries about regulatory changes, compliance requirements, and banking regulations based on the available information.

USER QUERY: {query}

AVAILABLE CONTEXT:
{context}

CONVERSATION HISTORY:
{chat_history}

REAL-TIME SEARCH RESULTS:
{search_results}

Guidelines for your response:
1. **Be Accurate**: Base your answers on verified regulatory information
2. **Be Clear**: Use simple, understandable language for banking customers
3. **Be Compliant**: Avoid giving specific legal advice; direct to professionals when needed
4. **Be Helpful**: Provide actionable information and next steps
5. **Be Contextual**: Consider the conversation history for personalized responses

Structure your response:
- Start with a direct answer to the question
- Provide relevant details from regulatory context
- Include any important deadlines or requirements
- Suggest next steps or who to contact if needed
- Reference the source of information when possible

If the query mentions "recent" or "latest" information, prioritize the real-time search results.
Always maintain a professional, helpful tone appropriate for banking customers.

Response:
"""
        )

        # Define the suggestions prompt
        self.suggestions_prompt = PromptTemplate(
            input_variables=["query", "response", "context"],
            template="""

Based on the user's query and your response, generate 2-3 relevant follow-up questions or related queries that the user might find helpful.

USER QUERY: {query}

YOUR RESPONSE: {response}

AVAILABLE CONTEXT:
{context}

Guidelines for suggestions:
1. **Relevance**: Questions should be directly related to the current topic
2. **Progressive**: Each suggestion should build on or expand the current conversation
3. **Practical**: Focus on questions customers commonly ask in banking/regulatory contexts
4. **Varied**: Provide different angles - some specific, some general
5. **Actionable**: Questions that lead to practical next steps

Generate exactly 2-3 concise, natural-sounding questions that would be the logical next things a banking customer might want to know.

Format your response as a simple JSON array of strings:
["Question 1?", "Question 2?", "Question 3?"]

Suggestions:
"""
        )

    def generate_suggestions(self, query: str, response: str, context: str) -> List[str]:
        """
        Generate follow-up suggestions based on the query and response.

        Args:
            query: Original user query
            response: AI response to the query
            context: Available context information

        Returns:
            List of suggested follow-up questions
        """
        try:
            # Format the suggestions prompt
            prompt_text = self.suggestions_prompt.format(
                query=query,
                response=response,
                context=context[:1000]  # Limit context to avoid token limits
            )

            # Generate suggestions
            suggestions_response = self.llm.invoke(prompt_text)

            # Parse JSON response
            suggestions_text = suggestions_response.content.strip()

            # Clean up the response if it has markdown formatting
            if suggestions_text.startswith("```json"):
                suggestions_text = suggestions_text[7:]
            if suggestions_text.endswith("```"):
                suggestions_text = suggestions_text[:-3]

            suggestions_text = suggestions_text.strip()

            # Parse JSON
            suggestions = json.loads(suggestions_text)

            # Validate and return
            if isinstance(suggestions, list) and len(suggestions) >= 2:
                return suggestions[:3]  # Return up to 3 suggestions
            else:
                # Fallback suggestions if parsing fails
                return self._generate_fallback_suggestions(query)

        except Exception as e:
            logger.error(f"Error generating suggestions: {e}")
            return self._generate_fallback_suggestions(query)

    def _generate_fallback_suggestions(self, query: str) -> List[str]:
        """
        Generate basic fallback suggestions based on common banking topics.

        Args:
            query: Original query to base suggestions on

        Returns:
            List of fallback suggestions
        """
        query_lower = query.lower()

        # Common banking regulatory topics and their follow-up questions
        topic_suggestions = {
            "kyc": [
                "What documents do I need for KYC verification?",
                "How long does KYC verification usually take?",
                "What happens if my KYC verification is delayed?"
            ],
            "compliance": [
                "What are the main compliance requirements for my account?",
                "How can I ensure I'm meeting all compliance standards?",
                "Who can I contact for compliance-related questions?"
            ],
            "account": [
                "What types of accounts are affected by these changes?",
                "How do these changes affect my existing account?",
                "Are there any fees associated with account updates?"
            ],
            "deadline": [
                "What is the exact deadline for compliance?",
                "What happens if I miss the deadline?",
                "Are there any extensions available?"
            ],
            "default": [
                "Can you explain this in simpler terms?",
                "What should I do next?",
                "Who can I contact for more specific guidance?"
            ]
        }

        # Find matching topic
        for topic, suggestions in topic_suggestions.items():
            if topic in query_lower and topic != "default":
                return suggestions

        return topic_suggestions["default"]

    def clean_markdown_formatting(self, text: str) -> str:
        """
        Clean up markdown formatting symbols to make responses more readable.
        Preserves numbered lists and basic structure while removing unwanted symbols.

        Args:
            text: Raw text with markdown formatting

        Returns:
            Clean text without markdown symbols
        """
        import re

        # Remove markdown headers but keep the text (### Header -> Header)
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)

        # Remove markdown bold/italic (**text** -> text, *text* -> text)
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        text = re.sub(r'\*(.*?)\*', r'\1', text)

        # Remove markdown links [text](url) -> text
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

        # Remove markdown code blocks but keep the content
        text = re.sub(r'```[^\n]*\n(.*?)\n```', r'\1', text, flags=re.DOTALL)

        # Remove inline code backticks (`code` -> code)
        text = re.sub(r'`([^`]+)`', r'\1', text)

        # Clean up excessive whitespace but preserve paragraph structure
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Remove horizontal rules (--- or ***)
        text = re.sub(r'^[-*_]{3,}$', '', text, flags=re.MULTILINE)

        return text.strip()

    def answer_query(self, query: str, user_id: str = "default") -> Dict[str, Any]:
        """
        Answer a user query using available knowledge and real-time search.

        Args:
            query: User's question
            user_id: Unique identifier for the user (for conversation tracking)

        Returns:
            Dictionary containing the answer and metadata
        """
        try:
            # Check if query requires real-time search
            needs_search = self._should_search_realtime(query)

            # Get real-time search results if needed
            search_results = ""
            if needs_search:
                search_results = self._perform_realtime_search(query)

            # Get relevant context from knowledge base
            context = self._get_relevant_context(query)

            # Get conversation history
            chat_history = self._get_formatted_history()

            # Format the prompt
            prompt_text = self.query_prompt.format(
                query=query,
                context=context,
                chat_history=chat_history,
                search_results=search_results
            )

            # Generate response
            response = self.llm.invoke(prompt_text)

            # Update conversation memory
            self._update_memory(query, response.content)

            # Clean up markdown formatting from the response
            cleaned_answer = self.clean_markdown_formatting(response.content)

            # Generate follow-up suggestions
            suggestions = self.generate_suggestions(query, cleaned_answer, self.clean_markdown_formatting(context))

            # Prepare response metadata
            response_metadata = {
                "query": query,
                "answer": cleaned_answer,
                "suggestions": suggestions,
                "timestamp": datetime.now().isoformat(),
                "used_realtime_search": needs_search,
                "context_sources": len(context.split('\n\n')) if context else 0,
                "user_id": user_id
            }

            logger.info(f"Answered query for user {user_id}: {query[:50]}...")
            return response_metadata

        except Exception as e:
            logger.error(f"Error answering query: {e}")
            return self._generate_error_response(query, str(e))

    def _should_search_realtime(self, query: str) -> bool:
        """
        Determine if the query requires real-time search.

        Args:
            query: User's query

        Returns:
            Boolean indicating if real-time search is needed
        """
        query_lower = query.lower()

        # Keywords that indicate need for recent information
        realtime_keywords = [
            "recent", "latest", "current", "new", "update", "change",
            "today", "this week", "this month", "breaking", "news"
        ]

        # Check for temporal keywords
        for keyword in realtime_keywords:
            if keyword in query_lower:
                return True

        # Check for date-related patterns
        date_patterns = [
            r'\d{1,2}/\d{1,2}/\d{4}',  # MM/DD/YYYY
            r'\d{4}-\d{1,2}-\d{1,2}',  # YYYY-MM-DD
            r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s+\d{4}\b'
        ]

        for pattern in date_patterns:
            if re.search(pattern, query_lower):
                return True

        return False

    def _perform_realtime_search(self, query: str) -> str:
        """
        Perform real-time search using DuckDuckGo.

        Args:
            query: Search query

        Returns:
            Formatted search results
        """
        try:
            # Enhance query for regulatory search
            search_query = f"banking regulatory {query} site:.gov OR site:.org OR site:.com/banking"

            # Perform search
            results = list(self.ddgs.text(search_query, max_results=5))

            # Format results
            formatted_results = "REAL-TIME SEARCH RESULTS:\n\n"
            for i, result in enumerate(results, 1):
                formatted_results += f"{i}. {result['title']}\n"
                formatted_results += f"   Source: {result['href']}\n"
                formatted_results += f"   Summary: {result['body'][:200]}...\n\n"

            return formatted_results

        except Exception as e:
            logger.error(f"Error performing real-time search: {e}")
            return "Unable to perform real-time search at this time."

    def _get_relevant_context(self, query: str) -> str:
        """
        Get relevant context from the knowledge base.

        Args:
            query: User's query

        Returns:
            Formatted context string
        """
        try:
            # Search FAQs
            faq_results = self.knowledge_base.search_faqs(
                query=query,
                embedding_func=self.embeddings.embed_query,
                top_k=3
            )

            # Get regulatory texts
            regulatory_texts = self.knowledge_base.get_all_regulatory_texts()

            # Format context
            context_parts = []

            # Add FAQ context
            if faq_results:
                context_parts.append("RELEVANT FAQs:")
                for faq in faq_results:
                    context_parts.append(f"Q: {faq['question']}")
                    context_parts.append(f"A: {faq['answer']}")
                    context_parts.append("")

            # Add regulatory context (most recent first)
            if regulatory_texts:
                recent_texts = sorted(
                    regulatory_texts,
                    key=lambda x: x["metadata"].get("timestamp", 0),
                    reverse=True
                )[:2]  # Limit to 2 most recent

                context_parts.append("RECENT REGULATORY INFORMATION:")
                for text_info in recent_texts:
                    context_parts.append(f"Source: {text_info['metadata'].get('source', 'Unknown')}")
                    context_parts.append(f"Date: {text_info['metadata'].get('date', 'Unknown')}")
                    context_parts.append(f"Content: {text_info['content'][:500]}...")
                    context_parts.append("")

            return "\n".join(context_parts)

        except Exception as e:
            logger.error(f"Error getting relevant context: {e}")
            return "Limited regulatory context available."

    def _get_formatted_history(self) -> str:
        """
        Get formatted conversation history.

        Returns:
            Formatted chat history string
        """
        try:
            history = self.memory.chat_memory.messages

            if not history:
                return "No previous conversation."

            formatted_history = []
            for msg in history[-6:]:  # Last 6 messages for context
                if isinstance(msg, HumanMessage):
                    formatted_history.append(f"User: {msg.content}")
                elif isinstance(msg, AIMessage):
                    formatted_history.append(f"Assistant: {msg.content}")

            return "\n".join(formatted_history)

        except Exception as e:
            logger.error(f"Error formatting chat history: {e}")
            return "Conversation history unavailable."

    def _update_memory(self, query: str, response: str):
        """
        Update conversation memory with the new interaction.

        Args:
            query: User's query
            response: Assistant's response
        """
        try:
            self.memory.chat_memory.add_user_message(query)
            self.memory.chat_memory.add_ai_message(response)
        except Exception as e:
            logger.error(f"Error updating memory: {e}")

    def _generate_error_response(self, query: str, error: str) -> Dict[str, Any]:
        """
        Generate an error response when query processing fails.

        Args:
            query: Original query
            error: Error message

        Returns:
            Error response dictionary
        """
        # Generate basic suggestions even for errors
        suggestions = self._generate_fallback_suggestions(query)

        error_message = "I apologize, but I'm experiencing technical difficulties. Please try again or contact our customer service team for assistance with your regulatory inquiry."

        return {
            "query": query,
            "answer": self.clean_markdown_formatting(error_message),
            "suggestions": suggestions,
            "timestamp": datetime.now().isoformat(),
            "error": error,
            "used_realtime_search": False,
            "context_sources": 0
        }

    def clear_memory(self, user_id: str = "default"):
        """
        Clear conversation memory for a specific user.

        Args:
            user_id: User identifier
        """
        try:
            self.memory.clear()
            logger.info(f"Cleared conversation memory for user {user_id}")
        except Exception as e:
            logger.error(f"Error clearing memory: {e}")

    def get_conversation_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current conversation.

        Returns:
            Conversation summary
        """
        try:
            messages = self.memory.chat_memory.messages
            return {
                "total_messages": len(messages),
                "conversation_length": len(" ".join([msg.content for msg in messages])),
                "last_interaction": messages[-1].content if messages else None,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting conversation summary: {e}")
            return {"error": "Unable to generate summary"}
