"""Runtime configuration, read once from Lambda environment variables (set by Terraform)."""
import os

TABLE_NAME = os.environ.get("TABLE_NAME", "phytro-local")
WORKER_FUNCTION = os.environ.get("WORKER_FUNCTION", "")
MODEL_ID = os.environ.get("MODEL_ID", "us.amazon.nova-lite-v1:0")
GUARDRAIL_ID = os.environ.get("GUARDRAIL_ID", "")
GUARDRAIL_VERSION = os.environ.get("GUARDRAIL_VERSION", "DRAFT")
OFF_BASE_URL = os.environ.get("OFF_BASE_URL", "https://world.openfoodfacts.org")
OFF_USER_AGENT = os.environ.get("OFF_USER_AGENT", "PhyTro/1.0 (aico-mini-capstone)")
CACHE_TTL_HOURS = int(os.environ.get("CACHE_TTL_HOURS", "72"))
JOB_TTL_HOURS = int(os.environ.get("JOB_TTL_HOURS", "24"))

# Nova Lite on-demand pricing (USD per 1M tokens) - used only for the cost dashboard estimate.
# Update if AWS changes pricing: https://aws.amazon.com/bedrock/pricing/
PRICE_IN_PER_M = float(os.environ.get("PRICE_IN_PER_M", "0.06"))
PRICE_OUT_PER_M = float(os.environ.get("PRICE_OUT_PER_M", "0.24"))

STORES = {
    "walmart": "Walmart",
    "target": "Target",
    "costco": "Costco",
    "kroger": "Kroger",
    "whole-foods": "Whole Foods",
    "trader-joe-s": "Trader Joe's",
    "any": "Any US store",
}

# UI category -> Open Food Facts category tag
CATEGORIES = {
    "coffee": {"label": "Coffee", "tag": "en:coffees", "emoji": "☕"},
    "cereal": {"label": "Cereal", "tag": "en:breakfast-cereals", "emoji": "🥣"},
    "bread": {"label": "Bread", "tag": "en:breads", "emoji": "🍞"},
    "yogurt": {"label": "Yogurt", "tag": "en:yogurts", "emoji": "🥛"},
    "chips": {"label": "Chips", "tag": "en:crisps", "emoji": "🥔"},
    "cookies": {"label": "Cookies", "tag": "en:biscuits", "emoji": "🍪"},
    "soda": {"label": "Soda", "tag": "en:sodas", "emoji": "🥤"},
    "juice": {"label": "Juice", "tag": "en:fruit-juices", "emoji": "🧃"},
    "peanut-butter": {"label": "Peanut butter", "tag": "en:peanut-butters", "emoji": "🥜"},
    "pasta-sauce": {"label": "Pasta sauce", "tag": "en:pasta-sauces", "emoji": "🍝"},
    "snack-bars": {"label": "Snack bars", "tag": "en:cereal-bars", "emoji": "🍫"},
    "candy": {"label": "Candy", "tag": "en:candies", "emoji": "🍬"},
    "plant-milk": {"label": "Plant milk", "tag": "en:plant-based-milk-alternatives", "emoji": "🌱"},
    "baby-food": {"label": "Baby food", "tag": "en:baby-foods", "emoji": "🍼"},
}
