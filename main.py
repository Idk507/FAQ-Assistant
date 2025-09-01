import logging
import asyncio
from typing import Dict, List, Any, Optional
from autogen import ConversableAgent, UserProxyAgent
from agents.faq_agent import FAQAgent
from agents.validation_agent import ValidationAgent
from agents.query_agent import QueryAgent
from utils.memory_storage import RegulatoryKnowledgeBase
from config.azure_config import AZURE_OPENAI_CONFIG

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RegulatoryFAQSystem:
    """
    Main system orchestrating the multi-agent regulatory FAQ generation and query answering.
    """

    def __init__(self):
        # Initialize knowledge base
        self.knowledge_base = RegulatoryKnowledgeBase()

        # Initialize agents
        self.faq_agent_instance = FAQAgent()
        self.validation_agent_instance = ValidationAgent()
        self.query_agent_instance = QueryAgent(self.knowledge_base)

        # Initialize AutoGen agents
        self._setup_autogen_agents()

        logger.info("Regulatory FAQ System initialized successfully")

    def _setup_autogen_agents(self):
        """Setup AutoGen agents for multi-agent orchestration."""

        # Azure OpenAI configuration for AutoGen
        azure_config = {
            "model": AZURE_OPENAI_CONFIG["gpt_deployment"],
            "api_key": AZURE_OPENAI_CONFIG["api_key"],
            "base_url": AZURE_OPENAI_CONFIG["endpoint"],
            "api_type": "azure",
            "api_version": AZURE_OPENAI_CONFIG["api_version"]
        }

        # FAQ Generation Agent
        self.faq_agent = ConversableAgent(
            name="FAQ_Agent",
            system_message="""You are a specialized agent for generating FAQs from regulatory texts.
            Your role is to analyze regulatory changes and create 3-5 clear, accurate FAQs in JSON format.
            Always respond with properly formatted JSON containing the FAQs.""",
            llm_config={
                "config_list": [azure_config]
            },
            human_input_mode="NEVER",
        )

        # Validation Agent
        self.validation_agent = ConversableAgent(
            name="Validation_Agent",
            system_message="""You are an expert validation agent specializing in regulatory compliance.
            Your role is to review FAQs for accuracy, legal compliance, and completeness.
            Simulate expert feedback from risk and legal teams.""",
            llm_config={
                "config_list": [azure_config]
            },
            human_input_mode="NEVER",
        )

        # Query Agent
        self.query_agent = ConversableAgent(
            name="Query_Agent",
            system_message="""You are a customer service agent specializing in regulatory queries.
            Answer customer questions about regulations using available knowledge and real-time search.
            Maintain conversational context and provide helpful, accurate responses.""",
            llm_config={
                "config_list": [azure_config]
            },
            human_input_mode="NEVER",
        )

        # User Proxy Agent
        self.user_proxy = UserProxyAgent(
            name="User_Proxy",
            human_input_mode="ALWAYS",
            code_execution_config=False,
        )

        # Register agent functions
        self._register_agent_functions()

    def _register_agent_functions(self):
        """Register functions for each agent."""
        # Note: AutoGen functions will be called directly through the agent instances
        # rather than registering them with decorators for this implementation
        pass

    async def process_regulatory_update(self, regulatory_text: str, context: str = "") -> Dict[str, Any]:
        """
        Process a regulatory update through the multi-agent system.

        Args:
            regulatory_text: The regulatory text to process
            context: Additional context about customer queries or patterns

        Returns:
            Dictionary containing the complete processing results
        """
        logger.info("Starting regulatory update processing...")

        try:
            # Step 1: Generate FAQs
            logger.info("Step 1: Generating FAQs...")
            faqs = self.faq_agent_instance.generate_faqs(regulatory_text, context)

            # Step 2: Validate FAQs
            logger.info("Step 2: Validating FAQs...")
            validation_results = self.validation_agent_instance.simulate_expert_workflow(
                faqs, regulatory_text
            )

            # Step 3: Store validated FAQs in knowledge base
            logger.info("Step 3: Storing FAQs in knowledge base...")
            approved_faqs = [
                faq for faq in faqs
                if validation_results["validation_feedback"].get(f"faq_{faqs.index(faq)}", {}).get("overall_approved", False)
            ]

            self.knowledge_base.add_faqs(approved_faqs, regulatory_text)

            # Step 4: Store regulatory text
            self.knowledge_base.add_regulatory_text(regulatory_text, "Regulatory Update")

            result = {
                "status": "success",
                "faqs_generated": len(faqs),
                "faqs_approved": len(approved_faqs),
                "validation_summary": validation_results["summary"],
                "recommendations": validation_results.get("recommendations", []),
                "approved_faqs": approved_faqs
            }

            logger.info(f"Regulatory update processing completed: {result}")
            return result

        except Exception as e:
            logger.error(f"Error processing regulatory update: {e}")
            return {
                "status": "error",
                "error_message": str(e),
                "faqs_generated": 0,
                "faqs_approved": 0
            }

    async def answer_customer_query(self, query: str, user_id: str = "default") -> Dict[str, Any]:
        """
        Answer a customer query using the Query Agent.

        Args:
            query: Customer's question
            user_id: Unique user identifier

        Returns:
            Query response
        """
        logger.info(f"Answering query for user {user_id}: {query[:50]}...")

        try:
            response = self.query_agent_instance.answer_query(query, user_id)
            return response
        except Exception as e:
            logger.error(f"Error answering customer query: {e}")
            return {
                "query": query,
                "answer": "I apologize, but I'm experiencing technical difficulties. Please try again later.",
                "error": str(e),
                "timestamp": None
            }

    def get_system_status(self) -> Dict[str, Any]:
        """Get the current system status."""
        return {
            "faqs_count": len(self.knowledge_base.faqs),
            "regulatory_texts_count": len(self.knowledge_base.regulatory_texts),
            "memory_status": "active" if hasattr(self.query_agent_instance, 'memory') else "inactive",
            "agents_status": "all_active"
        }

    def clear_knowledge_base(self):
        """Clear all stored knowledge (for testing/reset purposes)."""
        self.knowledge_base.clear_all()
        logger.info("Knowledge base cleared")


async def main():
    """Main function to demonstrate the regulatory FAQ system."""

    # Initialize the system
    system = RegulatoryFAQSystem()

    # Sample regulatory text
    sample_regulatory_text = """
    NEW REGULATORY REQUIREMENTS FOR DIGITAL BANKING ACCOUNTS

    Effective January 1, 2025, all digital banking platforms must implement enhanced customer verification procedures for account openings and transactions over $500.

    Key Changes:
    1. Enhanced KYC (Know Your Customer) requirements for digital account openings
    2. Mandatory biometric verification for transactions exceeding $500
    3. Real-time transaction monitoring and reporting
    4. Customer notification requirements for suspicious activities

    Compliance Deadline: December 31, 2024
    Non-compliance penalties: Up to $100,000 per violation
    """

    print("=== Regulatory FAQ Generation System ===\n")

    # Process regulatory update
    print("1. Processing regulatory update...")
    result = await system.process_regulatory_update(sample_regulatory_text)

    print(f"   Status: {result['status']}")
    print(f"   FAQs Generated: {result['faqs_generated']}")
    print(f"   FAQs Approved: {result['faqs_approved']}")
    print(f"   Validation Summary: {result['validation_summary']}")

    if result['recommendations']:
        print("   Recommendations:")
        for rec in result['recommendations']:
            print(f"   - {rec}")

    print("\n2. Testing Query Agent...")

    # Test queries
    test_queries = [
        "What are the new requirements for digital banking accounts?",
        "When do these regulatory changes take effect?",
        "What happens if I don't comply with these requirements?",
        "How will this affect my current banking transactions?"
    ]

    for query in test_queries:
        print(f"\nQuery: {query}")
        response = await system.answer_customer_query(query)
        print(f"Answer: {response['answer'][:200]}...")

    print("\n3. System Status:")
    status = system.get_system_status()
    print(f"   FAQs in Knowledge Base: {status['faqs_count']}")
    print(f"   Regulatory Texts Stored: {status['regulatory_texts_count']}")
    print(f"   Memory Status: {status['memory_status']}")

    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    # Run the demo
    asyncio.run(main())
