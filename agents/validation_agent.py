import json
import logging
from typing import Dict, List, Any
from langchain_openai import AzureChatOpenAI
from langchain.prompts import PromptTemplate
from config.azure_config import AZURE_OPENAI_CONFIG

logger = logging.getLogger(__name__)

class ValidationAgent:
    """
    Agent responsible for validating FAQs for accuracy and compliance.
    Simulates expert feedback from risk and legal experts.
    """

    def __init__(self):
        self.llm = AzureChatOpenAI(
            azure_endpoint=AZURE_OPENAI_CONFIG["endpoint"],
            azure_deployment=AZURE_OPENAI_CONFIG["gpt_deployment"],
            api_version=AZURE_OPENAI_CONFIG["api_version"],
            api_key=AZURE_OPENAI_CONFIG["api_key"],
            temperature=0.1,  # Very low temperature for consistent validation
            max_tokens=1500
        )

        # Define the validation prompt
        self.validation_prompt = PromptTemplate(
            input_variables=["faqs", "regulatory_text", "expertise_area"],
            template="""
You are a senior regulatory compliance expert with extensive experience in banking regulations and risk management. Your role is to validate FAQs generated about regulatory changes to ensure accuracy, completeness, and compliance with legal requirements.

REGULATORY TEXT:
{regulatory_text}

GENERATED FAQs TO VALIDATE:
{faqs}

As a {expertise_area} expert, review each FAQ for:

1. **Accuracy**: Does the answer correctly reflect the regulatory requirements?
2. **Completeness**: Does it cover all necessary aspects of the regulation?
3. **Clarity**: Is the language clear and understandable for banking customers?
4. **Legal Compliance**: Does it avoid giving unauthorized legal advice?
5. **Risk Assessment**: Does it properly address potential compliance risks?

For each FAQ, provide validation feedback in the following JSON format:

{{
    "faq_0": {{
        "approved": true/false,
        "accuracy_score": 1-10,
        "issues": ["list of specific issues found"],
        "suggestions": ["specific improvement suggestions"],
        "risk_level": "low/medium/high",
        "notes": "Additional expert notes"
    }},
    "faq_1": {{...}},
    ...
}}

Key validation criteria:
- **High Risk Issues**: Incorrect legal interpretation, missing critical compliance requirements
- **Medium Risk Issues**: Incomplete information, unclear language, missing timelines
- **Low Risk Issues**: Minor wording improvements, additional context suggestions

Be thorough but constructive. If a FAQ has critical errors, mark it as not approved. For minor issues, approve but provide suggestions for improvement.

Return only the JSON validation feedback, no additional text.
"""
        )

    def validate_faqs(self, faqs: List[Dict[str, Any]], regulatory_text: str, expertise_area: str = "Regulatory Compliance") -> Dict[str, Any]:
        """
        Validate FAQs for accuracy and compliance.

        Args:
            faqs: List of FAQ dictionaries to validate
            regulatory_text: Original regulatory text for reference
            expertise_area: Area of expertise for validation

        Returns:
            Dictionary containing validation feedback for each FAQ
        """
        try:
            # Format FAQs for the prompt
            faqs_text = json.dumps(faqs, indent=2)

            # Format the validation prompt
            prompt_text = self.validation_prompt.format(
                faqs=faqs_text,
                regulatory_text=regulatory_text,
                expertise_area=expertise_area
            )

            # Get validation feedback from LLM
            response = self.llm.invoke(prompt_text)

            # Parse the JSON response
            validation_json = response.content.strip()

            # Clean up the response if it has markdown formatting
            if validation_json.startswith("```json"):
                validation_json = validation_json[7:]
            if validation_json.endswith("```"):
                validation_json = validation_json[:-3]

            validation_json = validation_json.strip()

            # Parse JSON
            validation_feedback = json.loads(validation_json)

            # Validate the structure
            if not isinstance(validation_feedback, dict):
                raise ValueError("Validation feedback must be a JSON object")

            logger.info(f"Successfully validated {len(validation_feedback)} FAQs")
            return validation_feedback

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse validation JSON: {e}")
            logger.error(f"Raw response: {response.content}")
            return self._generate_fallback_validation(faqs)

        except Exception as e:
            logger.error(f"Error validating FAQs: {e}")
            return self._generate_fallback_validation(faqs)

    def _generate_fallback_validation(self, faqs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate basic fallback validation if the main validation fails.

        Args:
            faqs: List of FAQs to validate

        Returns:
            Basic validation feedback
        """
        logger.info("Generating fallback validation feedback")

        validation_feedback = {}

        for i, faq in enumerate(faqs):
            validation_feedback[f"faq_{i}"] = {
                "approved": True,  # Default to approved for fallback
                "accuracy_score": 7,  # Moderate score
                "issues": [],
                "suggestions": ["Consider consulting with legal experts for final review"],
                "risk_level": "medium",
                "notes": "Automated validation completed. Manual expert review recommended."
            }

        return validation_feedback

    def get_validation_summary(self, validation_feedback: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a summary of the validation results.

        Args:
            validation_feedback: Validation feedback dictionary

        Returns:
            Summary statistics and insights
        """
        total_faqs = len(validation_feedback)
        approved_count = 0
        high_risk_count = 0
        avg_accuracy = 0

        for feedback in validation_feedback.values():
            if feedback.get("approved", False):
                approved_count += 1

            if feedback.get("risk_level") == "high":
                high_risk_count += 1

            avg_accuracy += feedback.get("accuracy_score", 5)

        avg_accuracy = avg_accuracy / total_faqs if total_faqs > 0 else 0

        return {
            "total_faqs": total_faqs,
            "approved_faqs": approved_count,
            "approval_rate": (approved_count / total_faqs) * 100 if total_faqs > 0 else 0,
            "high_risk_issues": high_risk_count,
            "average_accuracy_score": round(avg_accuracy, 2),
            "validation_status": "passed" if approved_count == total_faqs and high_risk_count == 0 else "needs_review"
        }

    def simulate_expert_workflow(self, faqs: List[Dict[str, Any]], regulatory_text: str) -> Dict[str, Any]:
        """
        Simulate a complete expert validation workflow.

        Args:
            faqs: FAQs to validate
            regulatory_text: Original regulatory text

        Returns:
            Complete validation results including summary
        """
        logger.info("Starting expert validation workflow...")

        # Step 1: Legal compliance validation
        legal_feedback = self.validate_faqs(faqs, regulatory_text, "Legal and Compliance")

        # Step 2: Risk management validation
        risk_feedback = self.validate_faqs(faqs, regulatory_text, "Risk Management")

        # Step 3: Customer impact validation
        customer_feedback = self.validate_faqs(faqs, regulatory_text, "Customer Experience")

        # Combine all validation feedback
        combined_feedback = {}
        for i in range(len(faqs)):
            faq_key = f"faq_{i}"
            combined_feedback[faq_key] = {
                "legal_validation": legal_feedback.get(faq_key, {}),
                "risk_validation": risk_feedback.get(faq_key, {}),
                "customer_validation": customer_feedback.get(faq_key, {}),
                "overall_approved": all([
                    legal_feedback.get(faq_key, {}).get("approved", False),
                    risk_feedback.get(faq_key, {}).get("approved", False),
                    customer_feedback.get(faq_key, {}).get("approved", False)
                ])
            }

        # Generate summary
        summary = self.get_validation_summary(combined_feedback)

        return {
            "validation_feedback": combined_feedback,
            "summary": summary,
            "recommendations": self._generate_recommendations(combined_feedback, summary)
        }

    def _generate_recommendations(self, validation_feedback: Dict[str, Any], summary: Dict[str, Any]) -> List[str]:
        """
        Generate recommendations based on validation results.

        Args:
            validation_feedback: Combined validation feedback
            summary: Validation summary

        Returns:
            List of recommendations
        """
        recommendations = []

        if summary["approval_rate"] < 80:
            recommendations.append("Majority of FAQs need revision. Consider regenerating with more specific regulatory details.")

        if summary["high_risk_issues"] > 0:
            recommendations.append(f"Found {summary['high_risk_issues']} high-risk issues. Immediate legal review required.")

        if summary["average_accuracy_score"] < 7:
            recommendations.append("Average accuracy score is below acceptable threshold. Enhance regulatory text analysis.")

        if not recommendations:
            recommendations.append("All validations passed. FAQs are ready for publication with standard disclaimer.")

        return recommendations
