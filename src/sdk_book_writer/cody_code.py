from agents import Agent, OpenAIChatCompletionsModel, Runner, set_tracing_disabled
from agents.run import RunConfig
from openai import AsyncOpenAI
from dotenv import load_dotenv
from sdk_book_writer.model import BookOutline, Book
from sdk_book_writer.tool import search_tool
from sdk_book_writer.save_chapters import save_book_chapter, save_book_outline
import os, asyncio

set_tracing_disabled(True)
load_dotenv()

base_url = os.getenv('BASE_URL')
api_key = os.getenv('API_KEY')
model_name = os.getenv('MODEL_NAME')

# Create a standard client
client = AsyncOpenAI(
    api_key=api_key,
    base_url=base_url
)

# Patch the chat.completions.create method directly
original_create = client.chat.completions.create

async def patched_create(*args, **kwargs):
    # Remove problematic parameters
    if 'metadata' in kwargs:
        del kwargs['metadata']
    if 'store' in kwargs:
        del kwargs['store']
    
    # Handle the response_format differently
    if 'response_format' in kwargs:
        # Add instructions about the required JSON structure
        if 'messages' in kwargs and kwargs['messages']:
            system_msg_index = None
            for i, msg in enumerate(kwargs['messages']):
                if msg.get('role') == 'system':
                    system_msg_index = i
                    break
            
            # Add instructions to the system message
            json_instruction = "\nIMPORTANT: Your response MUST be a valid JSON object. Do NOT include control characters, markdown formatting, code blocks, or any explanatory text."
            
            if system_msg_index is not None:
                kwargs['messages'][system_msg_index]['content'] += json_instruction
            else:
                kwargs['messages'].insert(0, {
                    'role': 'system',
                    'content': json_instruction
                })
        
        # Remove the response_format parameter
        del kwargs['response_format']
    
    # Remove any other OpenAI-specific parameters
    openai_specific_params = ['parallel_tool_calls', 'reasoning_effort', 'stream_options']
    for param in openai_specific_params:
        if param in kwargs:
            del kwargs[param]
    
    response = await original_create(*args, **kwargs)
    
    # Post-process the response to clean up any issues
    if hasattr(response, 'choices') and response.choices:
        for choice in response.choices:
            if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                content = choice.message.content
                
                # Remove markdown code blocks if present
                if content and '```' in content:
                    import re
                    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
                    if json_match:
                        content = json_match.group(1).strip()
                
                # Clean up control characters
                import re
                content = re.sub(r'[\x00-\x1F\x7F]', '', content)
                
                # Update the content
                choice.message.content = content
    
    return response

# Apply the patch
client.chat.completions.create = patched_create

model = OpenAIChatCompletionsModel(
    model=model_name,
    openai_client=client
)

config = RunConfig(
    model=model,
    model_provider=client,
    tracing_disabled=True
)

# Replace the generate_book_outline Agent definition with this:
generate_book_outline = Agent(
    name="Book Writer",
    handoff_description = "Specialist agent for researching topics and gathering " \
    "high-quality information to support course outline creation",
    instructions = """
    You are a research assistant tasked with gathering essential information 
    for creating a high-quality book outline.
    IMPORTANT: Your response MUST be a valid JSON object with EXACTLY this structure:
    {
      "chapters": [
        {
          "title": "Chapter Title",
          "description": "Chapter description with details about what this chapter covers"
        },
        ...more chapters...
      ]
    }
     
    When creating the outline:
    1. Research the provided topic thoroughly
    2. Focus on collecting the most important and relevant information
    3. Create 6-10 logical chapters that flow well together
    4. For each chapter, provide a clear title and detailed description
    5. Ensure the outline covers all important aspects of the topic
    
    # Do NOT include any explanatory text, markdown formatting, or code blocks.
    # ONLY return the JSON object with the exact structure shown above.
    """,
    model=model,
    tools=[search_tool],
    output_type=BookOutline
)

# Replace the write_book Agent definition with this:
write_book = Agent(
    name="Book_writer",
    instructions = """
    You are a creative and detail-oriented book writing assistant. When generating content, please adhere to the following:

    - Generate a valid JSON object with the following structure:
    {
        "chapters": [
        {
            "chapter_title": "Chapter Title",
            "content": "Full chapter content goes here with all newline characters represented as \\n"
        }
        ]
    }
    
    - DO NOT include any markdown, extra text, or comments.
    - Ensure that the "content" field is properly escaped (i.e., all newline characters as \\n, quotes as \\").
    - Ensure the JSON is **complete** and well-formed, with no additional characters after the final closing brace.

    Please proceed to generate a chapter on the topic of 'Front-End Frameworks and Libraries,' including detailed content and examples as specified.
    """,
    model=model,
    tools=[search_tool],
    handoffs=[generate_book_outline],
    output_type=Book
)

# Function to escape special characters for JSON compatibility
def escape_json_string(text):
    return text.replace("\n", "\\n").replace("\"", "\\\"")

async def main():
    try:
        # Single book topic for the full flow
        query = "Exploring the latest trend in Modern Web Development and it's "\
            "application in Real World Projects"

        
        print("\n" + "=" * 60)
        print(f"QUERY: {query}")
        print(f"Starting with query: {query}")
        
        # Step 1: Generate the outline
        print("Generating book outline...")
        outline_result = await Runner.run(generate_book_outline, query, run_config=config)
        outline = outline_result.final_output
        
        print("Book outline generated successfully")
        print("\n🧭 BOOK OUTLINE:\n")
        for i, chapter in enumerate(outline.chapters, 1):
            print(f"{i}. {chapter.title}")
            print(f"   📄 {chapter.description}\n")
        
        # Step 2: Write one chapter based on the outline
        print("Writing book chapter...")
        
        # In the main function, replace this line:
        write_input = outline  # Pass the full BookOutline to the write_book agent

       # Alternative approach using a string input
        write_input = f"Create a book chapter based on this outline: {outline.model_dump_json()}"


        # Make sure to pass the config here too
        book_result = await Runner.run(write_book, write_input, run_config=config)
        book = book_result.final_output
        
        print("Book chapter written successfully")

        if book.chapters:
            for chapter in book.chapters:
                # Ensure that content is escaped properly before processing
                if hasattr(chapter, 'content'):
                    chapter.content = escape_json_string(chapter.content)
            
        print("\n📝 WRITTEN CHAPTER (Processed):\n")

        if book.chapters:
            for chapter in book.chapters:
                # Accessing content via dot notation, not by indexing
                if hasattr(chapter, 'content'):
                    chapter.content = escape_json_string(chapter.content)
        
        print("\n📝 WRITTEN CHAPTER (Processed):\n")

        # Print the written chapter
        print("\n📝 WRITTEN CHAPTER:\n")
        if book.chapters:
            chapter = book.chapters[0]
            print(f"📎 Chapter Title: {chapter.chapter_title}\n")
            print(chapter.content)
        else:
            print("⚠️ No chapter content was generated.")
            print("No chapter content was generated")

        # Save outputs using simplified helper functions
        save_book_outline(outline)
        save_book_chapter(book)
        
    except Exception as e:
        print(f"Error in main function: {str(e)}")
        import traceback
        print(traceback.format_exc())
        print(f"ERROR: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())

