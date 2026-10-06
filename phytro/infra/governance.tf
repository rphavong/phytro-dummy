# Bedrock Guardrail, applied by the worker with the ApplyGuardrail API to:
#   INPUT  - crowd-sourced label text before any agent reads it (prompt-injection shield)
#   OUTPUT - the Shopper Advocate's final answer before the shopper sees it
resource "aws_bedrock_guardrail" "safety" {
  count                     = var.enable_guardrail ? 1 : 0
  name                      = "${local.name}-guardrail"
  description               = "PhyTro: block prompt attacks, harmful content and medical diagnosis/treatment advice"
  blocked_input_messaging   = "This product's label text was blocked by PhyTro's safety filter."
  blocked_outputs_messaging = "PhyTro can compare ingredients and regulations, but it can't diagnose conditions or recommend treatments. Please ask a doctor or registered dietitian."

  content_policy_config {
    filters_config {
      type            = "PROMPT_ATTACK"
      input_strength  = "HIGH"
      output_strength = "NONE" # AWS requires NONE for prompt-attack output
    }
    filters_config {
      type            = "HATE"
      input_strength  = "MEDIUM"
      output_strength = "MEDIUM"
    }
    filters_config {
      type            = "INSULTS"
      input_strength  = "MEDIUM"
      output_strength = "MEDIUM"
    }
    filters_config {
      type            = "SEXUAL"
      input_strength  = "MEDIUM"
      output_strength = "MEDIUM"
    }
    filters_config {
      type            = "VIOLENCE"
      input_strength  = "MEDIUM"
      output_strength = "MEDIUM"
    }
  }

  topic_policy_config {
    topics_config {
      name       = "medical-diagnosis-or-treatment"
      type       = "DENY"
      definition = "Diagnosing a person's disease or symptoms, or recommending medications, doses, or medical treatments for a person."
      examples = [
        "Do I have celiac disease if bread makes me bloated?",
        "How much aspartame can I give my child with PKU?",
        "Which medicine should I take for a reaction to Red 40?",
      ]
    }
  }
}

resource "aws_bedrock_guardrail_version" "safety" {
  count         = var.enable_guardrail ? 1 : 0
  guardrail_arn = aws_bedrock_guardrail.safety[0].guardrail_arn
  description   = "Managed by Terraform"
}
