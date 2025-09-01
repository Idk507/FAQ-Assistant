import json
import logging
from typing import Dict, List, Any
from langchain_openai import AzureChatOpenAI
from langchain.prompts import PromptTemplate
from config.azure_config import AZURE_OPENAI_CONFIG

logger = logging.getLogger(__name__)

class FAQAgent:
    """
    Agent responsible for generating FAQs from regulatory text and context.
    Generates 3-5 FAQs in JSON format.
    """

    def __init__(self):
        self.llm = AzureChatOpenAI(
            azure_endpoint=AZURE_OPENAI_CONFIG["endpoint"],
            azure_deployment=AZURE_OPENAI_CONFIG["gpt_deployment"],
            api_version=AZURE_OPENAI_CONFIG["api_version"],
            api_key=AZURE_OPENAI_CONFIG["api_key"],
            temperature=0.3,  # Lower temperature for more consistent output
            max_tokens=2000
        )

        # Define the FAQ generation prompt
        self.faq_prompt = PromptTemplate(
            input_variables=["regulatory_text", "context"],
            template="""
You are an expert regulatory compliance specialist tasked with generating clear, accurate FAQs for banking customers regarding regulatory changes.

REGULATORY TEXT:
{regulatory_text}

ADDITIONAL CONTEXT:
{context}

Based on the regulatory text above, generate 3-5 frequently asked questions (FAQs) that customers might have about these changes. Each FAQ should include:

1. A clear, concise question that a customer would actually ask
2. A comprehensive but easy-to-understand answer
3. The specific regulatory impact or requirement
4. Any actions the customer might need to take

Format your response as a valid JSON array with the following structure:
[
    {{
        "question": "Customer's question here?",
        "answer": "Detailed answer explaining the regulatory requirement and customer impact.",
        "category": "compliance/banking/accounts/etc",
        "priority": "high/medium/low",
        "regulatory_reference": "Brief reference to the specific regulation"
    }}
]

Ensure the questions are practical and cover the most important aspects that would concern banking customers. Focus on:
- What changes are happening
- How it affects customers
- What actions customers need to take
- Deadlines or timelines
- Potential consequences of non-compliance

Generate exactly 3-5 FAQs and return only the JSON array, no additional text.
"""
        )

    def generate_faqs(self, regulatory_text: str, context: str = "") -> List[Dict[str, Any]]:
        """
        Generate FAQs from regulatory text.

        Args:
            regulatory_text: The regulatory text to analyze
            context: Additional context about customer queries or patterns

        Returns:
            List of FAQ dictionaries
        """
        try:
            # Format the prompt
            prompt_text = self.faq_prompt.format(
                regulatory_text=regulatory_text,
                context=context
            )

            # Generate FAQs using the LLM
            response = self.llm.invoke(prompt_text)

            # Parse the JSON response
            faq_json = response.content.strip()

            # Clean up the response if it has markdown formatting
            if faq_json.startswith("```json"):
                faq_json = faq_json[7:]
            if faq_json.endswith("```"):
                faq_json = faq_json[:-3]

            faq_json = faq_json.strip()

            # Parse JSON
            faqs = json.loads(faq_json)

            # Validate the structure
            if not isinstance(faqs, list):
                raise ValueError("Generated FAQs must be a JSON array")

            if not 3 <= len(faqs) <= 5:
                logger.warning(f"Generated {len(faqs)} FAQs, expected 3-5. Adjusting...")

            # Ensure each FAQ has required fields
            validated_faqs = []
            for faq in faqs:
                if isinstance(faq, dict) and "question" in faq and "answer" in faq:
                    # Add default values for missing fields
                    faq.setdefault("category", "regulatory")
                    faq.setdefault("priority", "medium")
                    faq.setdefault("regulatory_reference", "Regulatory Update")
                    validated_faqs.append(faq)

            logger.info(f"Successfully generated {len(validated_faqs)} FAQs")
            return validated_faqs[:5]  # Limit to 5 max

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse FAQ JSON: {e}")
            logger.error(f"Raw response: {response.content}")
            return self._generate_fallback_faqs(regulatory_text)

        except Exception as e:
            logger.error(f"Error generating FAQs: {e}")
            return self._generate_fallback_faqs(regulatory_text)

    def _generate_fallback_faqs(self, regulatory_text: str) -> List[Dict[str, Any]]:
        """
        Generate basic fallback FAQs if the main generation fails.

        Args:
            regulatory_text: The regulatory text

        Returns:
            List of basic FAQ dictionaries
        """
        logger.info("Generating fallback FAQs")

        # Extract key terms from regulatory text (simple approach)
        text_lower = regulatory_text.lower()
        key_terms = []

        if "compliance" in text_lower or "regulation" in text_lower:
            key_terms.append("compliance")
        if "account" in text_lower:
            key_terms.append("account")
        if "customer" in text_lower:
            key_terms.append("customer")
        if "deadline" in text_lower or "date" in text_lower:
            key_terms.append("deadline")

        return [
            {
                "question": f"What are the key regulatory changes mentioned in the update?",
                "answer": f"The regulatory update covers important changes related to {', '.join(key_terms) if key_terms else 'banking regulations'}. Please review the full text for complete details.",
                "category": "regulatory",
                "priority": "high",
                "regulatory_reference": "Regulatory Update"
            },
            {
                "question": "How will these regulatory changes affect me as a customer?",
                "answer": "These changes may impact your banking relationship and require specific actions. We recommend contacting your relationship manager for personalized guidance.",
                "category": "customer_impact",
                "priority": "high",
                "regulatory_reference": "Customer Impact Assessment"
            },
            {
                "question": "What actions do I need to take to comply with these regulations?",
                "answer": "Specific compliance actions will depend on your account type and current status. Please review your account details and contact us if you need assistance.",
                "category": "compliance",
                "priority": "medium",
                "regulatory_reference": "Compliance Requirements"
            }
        ]

    def update_faqs_with_validation(self, faqs: List[Dict[str, Any]], validation_feedback: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Update FAQs based on validation feedback.

        Args:
            faqs: Original FAQs
            validation_feedback: Feedback from validation agent

        Returns:
            Updated FAQs
        """
        updated_faqs = []

        for i, faq in enumerate(faqs):
            feedback_key = f"faq_{i}"
            if feedback_key in validation_feedback:
                feedback = validation_feedback[feedback_key]

                # Apply validation feedback
                if feedback.get("approved", True):
                    faq["validated"] = True
                    faq["validation_notes"] = feedback.get("notes", "")
                else:
                    # If not approved, mark for revision
                    faq["needs_revision"] = True
                    faq["revision_notes"] = feedback.get("notes", "")

            updated_faqs.append(faq)

        return updated_faqs
