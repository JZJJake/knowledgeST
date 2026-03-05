import os
import json
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from typing import List, Optional

# Define the expected JSON structure using Pydantic (useful if we want to parse it later, or even instruct the model)
class TermExpansion(BaseModel):
    core_definition: str = Field(..., description="The core definition of the professional term.")
    search_terms: List[str] = Field(..., description="5 to 10 cross-domain search terms related to the professional term.")
    time_span: str = Field(..., description="A suggested time span for searching academic papers (e.g., '2015-2023').")

class DeepSeekAdapter:
    def __init__(self, api_key: Optional[str] = None):
        # DeepSeek uses OpenAI-compatible API
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "dummy_key")
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com/v1"  # Or standard DeepSeek endpoint
        )
        self.system_prompt = """You are an expert academic researcher and terminologist.
When given a professional term, you must return a strict JSON object with exactly three fields:
1. "core_definition": A clear, concise, and authoritative definition of the term.
2. "search_terms": An array of 5 to 10 strings representing cross-domain search terms or synonyms related to the term.
3. "time_span": A suggested string representing the time span for relevant academic papers (e.g., "2010-2024").

DO NOT output any markdown, conversational text, or explanations. ONLY output valid JSON matching the required schema.
"""

    async def get_semantic_expansion(self, term: str) -> TermExpansion:
        try:
            response = await self.client.chat.completions.create(
                model="deepseek-chat", # Use standard deepseek chat model
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"Analyze the term: {term}"}
                ],
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            # Parse the strict JSON structure
            data = json.loads(content)

            # Validate with Pydantic
            expansion = TermExpansion(**data)
            return expansion

        except Exception as e:
            print(f"Error fetching semantic expansion from DeepSeek: {e}")
            # Return a fallback/dummy for testing if the API key is missing or invalid
            return TermExpansion(
                core_definition=f"Fallback definition for {term} due to API error.",
                search_terms=[f"{term} analysis", f"{term} studies", f"Applied {term}", f"Theoretical {term}", f"{term} methodology"],
                time_span="2018-2024"
            )
