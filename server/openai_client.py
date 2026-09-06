import json
import os
from dotenv import load_dotenv
from server.database.models import ChatMessage
from openai import OpenAI

load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_KEY)
def openai_chat(message, history:list[ChatMessage]=[]):
    # make api call to open ai api and generate response and give it back to the user
    prev_history = [{"role": msg.role.value, "content": msg.message} for msg in history]
    messages  = [
        {
            "role": "system",
            "content": "you are helpful assistant that helps user to answer their queries, make sure you respond within 30 words max, make sure you dont answers which are not legally correct and ethically correct,ignore messages which are in medical field, just casually say cant answer"
        },
        *prev_history,
        {
            "role": "user",
            "content": message
        }
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
        )
        # print number of tokens being used for input and output
        print(f"Input tokens: {response.usage.prompt_tokens}, Output tokens: {response.usage.completion_tokens}")
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {e}"

def chunk_string(data:str, file_title) -> [dict]:
    # convert this string into chunks
    system_message = """
You are an expert in RAG system design and document chunking.

Your task is to convert the provided document content into meaningful, semantically coherent chunks that can be stored in a vector database and retrieved later for question answering.

The input may contain multiple sections and subsections.

## Chunking Rules

1. Identify the document's sections from the original content.
   - A section is typically represented by headings such as:
     "Section 1: Purpose and Scope"
     "Section 2: Password Complexity and Length Rules"
   - Preserve the section name exactly as it appears in the document.

2. Identify subsections belonging to each section.
   - A subsection is typically represented by headings such as:
     "1.1 Purpose"
     "1.2 Scope"
     "1.3 Definitions"
   - Preserve the subsection name exactly as it appears in the document.

3. Create one chunk for each subsection.

4. Each chunk must contain:
   - section: The parent section name.
   - subsection: The subsection name.
   - content: The complete content belonging to that subsection.
   - id: A deterministic identifier generated from the section and subsection.

5. The `content` field must:
   - Contain the actual content under the subsection.
   - Preserve the original meaning and important details.
   - Preserve lists, examples, rules, requirements, conditions, and references.
   - Not add information that is not present in the document.
   - Not summarize unless necessary to maintain coherence.
   - Not include the subsection heading itself because it is already represented by the `subsection` field.

6. If a subsection contains multiple paragraphs or bullet points, keep them together in the same chunk as long as they represent the same logical topic.

7. Do not split a subsection into multiple chunks unless the subsection is extremely large and contains clearly independent topics.

8. If a section contains content but has no explicit subsection, create one chunk with:
   - subsection = null
   - content = the content belonging directly to that section.

9. Ignore document-level metadata such as document ID, version, effective date, owner, and classification unless it belongs to a section/subsection. Do not create a chunk for metadata unless explicitly requested.

10. Do not merge different subsections into one chunk.

11. Preserve references to other sections because they may be important for RAG retrieval.
    Example:
    "See Section 3.1" should remain in the content.

12. Generate `id` deterministically using the section and subsection identifiers.
    Example:
    - Section 1 + subsection 1.1 → "section_1_subsection_1_1"
    - Section 1 + subsection 1.2 → "section_1_subsection_1_2"

13. The output must contain ONLY valid JSON.
    Do not include markdown fences, explanations, comments, or additional text.

## Output Format

Return an array of objects using exactly this structure:

[
  {
    "section": "Section 1: Purpose and Scope",
    "subsection": "1.1 Purpose",
    "content": "Actual content belonging to this subsection.",
    "id": "section_1_subsection_1_1"
  }
]

## Important Constraints

- Do not invent sections or subsections.
- Do not rename sections or subsections.
- Do not change the meaning of the source content.
- Do not duplicate content across chunks unless necessary for context.
- Every subsection should appear in exactly one chunk.
- Keep each chunk semantically self-contained enough to be useful for vector search.
- Return valid JSON only.
    """
    
    
    messages  = [
            {
                "role": "system",
                "content": system_message
            },
            
            {
                "role": "user",
                "content": data
            }
        ]
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            # passing body part along query to brain saying that you can use body parts based on need
            tools=[]
        )
        formated_response  = json.loads(response.choices[0].message.content)
        for c in formated_response:
            c["file"] = file_title
        return formated_response
    except Exception as e:
        print(f"chunking failed, size of input : {len()}, error : {e}")
        raise Exception(f"Error: {e}")


def compactMessages(history:list[ChatMessage] = []) -> str:
    # compact the messages into a single string
    compaction_input  = [{"role": msg.role.value, "content": msg.message} for msg in history]
    result = json.dumps(compaction_input)
    master_message = """
    OUTPUT FORMAT:
Return ONLY a compact plain-text summary.

Do NOT:
- Return JSON
- Return role/content pairs
- Repeat the conversation format
- Include "user:" or "assistant:" labels
- Include Markdown headings unless they materially improve clarity

Write the summary of the conversation,

The summary should be as short as possible while preserving information required for the next model to continue the conversation correctly.

Target approximately 20–30 percent of the original conversation's token count when possible.
"""
    
    
    messages  = [
            {
                "role": "system",
                "content": master_message
            },
            
            {
                "role": "user",
                "content": result
            }
        ]
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
        )
        # print number of tokens being used for input and output
        print(f"Input tokens: {response.usage.prompt_tokens}, Output tokens: {response.usage.completion_tokens}")
        print(f"Compaction successful, size of input : {len(result)}, size of output : {len(response.choices[0].message.content)}")
        print(f"APi response  : {response}")
        return response.choices[0].message.content
    except Exception as e:
        print(f"Compaction failed, size of input : {len(result)}, error : {e}")
        raise Exception(f"Error: {e}")
