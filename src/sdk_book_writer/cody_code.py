from agents import Agent, OpenAIChatCompletionsModel, Runner, set_tracing_disabled
from agents.run import RunConfig
from openai import AsyncOpenAI
from dotenv import load_dotenv
from sdk_book_writer.model import BookOutline, Book
from sdk_book_writer.tool import search_tool
from datetime import datetime
import os, asyncio, json, logging

logger = logging.getLogger("book_writer_debug")

set_tracing_disabled(True)
load_dotenv()

base_url = os.getenv('BASE_URL')
api_key = os.getenv('API_KEY')
model_name = os.getenv('MODEL_NAME')

logger.info(f"Using base_url: {base_url}")
logger.info(f"Using model: {model_name}")

# Create a standard client
client = AsyncOpenAI(
    api_key=api_key,
    base_url=base_url
)

# Patch the chat.completions.create method directly
original_create = client.chat.completions.create

# Replace the problematic logging section in the patched_create function with this:
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
    
    try:
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
    except Exception as e:
        logger.error(f"API call failed: {str(e)}")
        raise

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
      "chapters_outline": [
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
    
    Do NOT include any explanatory text, markdown formatting, or code blocks.
    ONLY return the JSON object with the exact structure shown above.
    """,
    model=model,
    tools=[search_tool],
    output_type=BookOutline
)

# Replace the write_book Agent definition with this:
write_book = Agent(
    name="Book_writer",
    instructions="""
    You are a creative and detail-oriented book writing assistant who helps 
    users turn their ideas into engaging, well-written content.
    
    IMPORTANT: Your response MUST be a valid JSON object with EXACTLY this structure:
    {
      "chapters": [
        {
          "chapter_title": "Chapter Title",
          "content": "Full chapter content goes here..."
        }
      ]
    }
    
    You can:
    1. Choose one chapter from the provided book outline
    2. Write high-quality, in-depth content for that chapter only
    3. Maintain a consistent tone and narrative style appropriate for the book
    
    Always be thoughtful, clear, and aligned with the user's vision for the book. 
    Focus on depth and quality rather than covering all chapters at once.
    
    When writing the chapter, consider:
    - The target audience and their level of understanding
    - The structure and goals of the overall book
    - The tone, style, and voice that fits the topic
    - Adding detail, examples, and insights that bring the content to life
    
    Important: Select one chapter from the outline that you believe is impactful 
    or foundational. Do **not** attempt to write the full book or 
    multiple chapters in one go, to avoid exhausting resources.
    
    Do NOT include any explanatory text, markdown formatting, or code blocks.
    ONLY return the JSON object with the exact structure shown above.
    """,
    model=model,
    tools=[search_tool],
    handoffs=[generate_book_outline],
    output_type=Book
)

async def main():
    try:
        # Single book topic for the full flow
        query = "Write a book on 'Agentic and Robotic AI Engineering'"
        
        print("\n" + "=" * 60)
        print(f"QUERY: {query}")
        logger.info(f"Starting with query: {query}")
        
        # Step 1: Generate the outline
        logger.info("Generating book outline...")
        outline_result = await Runner.run(generate_book_outline, query, run_config=config)
        outline = outline_result.final_output
        
        logger.info("Book outline generated successfully")
        print("\n🧭 BOOK OUTLINE:\n")
        for i, chapter in enumerate(outline.chapters_outline, 1):
            print(f"{i}. {chapter.title}")
            print(f"   📄 {chapter.description}\n")
        
        # Step 2: Write one chapter based on the outline
        logger.info("Writing book chapter...")
        
        # In the main function, replace this line:
        write_input = outline  # Pass the full BookOutline to the write_book agent

       # Alternative approach using a string input
        write_input = f"Create a book chapter based on this outline: {outline.model_dump_json()}"


        # Make sure to pass the config here too
        book_result = await Runner.run(write_book, write_input, run_config=config)
        book = book_result.final_output
        
        logger.info("Book chapter written successfully")
        # Print the written chapter
        print("\n📝 WRITTEN CHAPTER:\n")
        if book.chapters:
            chapter = book.chapters[0]
            print(f"📎 Chapter Title: {chapter.chapter_title}\n")
            print(chapter.content)
        else:
            print("⚠️ No chapter content was generated.")
            logger.warning("No chapter content was generated")

        # Create a directory to store the outputs if it doesn't exist
        output_dir = "book_outputs"
        os.makedirs(output_dir, exist_ok=True)

        # Generate a timestamp for unique filenames
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save the book outline to a professionally formatted text file
        outline_file = os.path.join(output_dir, f"outline_{timestamp}.txt")
        with open(outline_file, "w", encoding="utf-8") as f:
            f.write("# BOOK OUTLINE\n\n")
            
            # Add a title based on the first chapter's title (usually introduction)
            if outline.chapters_outline and len(outline.chapters_outline) > 0:
                book_title = outline.chapters_outline[0].title.split(':')[0] if ':' in outline.chapters_outline[0].title else outline.chapters_outline[0].title
                f.write(f"## {book_title.upper()}\n\n")
            
            # Write each chapter with proper formatting
            for i, chapter in enumerate(outline.chapters_outline, 1):
                f.write(f"### CHAPTER {i}: {chapter.title}\n\n")
                
                # Format the description with proper paragraphs
                # Split by periods followed by spaces and create paragraphs
                sentences = chapter.description.split('. ')
                paragraphs = []
                current_paragraph = []
                
                for sentence in sentences:
                    current_paragraph.append(sentence)
                    if len(current_paragraph) >= 2:  # Group sentences into paragraphs
                        paragraphs.append('. '.join(current_paragraph) + ('.' if not current_paragraph[-1].endswith('.') else ''))
                        current_paragraph = []
                
                # Add any remaining sentences
                if current_paragraph:
                    paragraphs.append('. '.join(current_paragraph) + ('.' if not current_paragraph[-1].endswith('.') else ''))
                
                # Write paragraphs with proper formatting
                for paragraph in paragraphs:
                    f.write(f"{paragraph}\n\n")
                
                # Add a separator between chapters except for the last one
                if i < len(outline.chapters_outline):
                    f.write("---\n\n")

        logger.info(f"Book outline saved to {outline_file}")
        print(f"\n✅ Book outline saved to {outline_file}")

        # Save the written chapter to a professionally formatted text file
        if book.chapters:
            chapter = book.chapters[0]
            chapter_file = os.path.join(output_dir, f"chapter_{timestamp}.txt")
            
            with open(chapter_file, "w", encoding="utf-8") as f:
                # Add a proper chapter heading
                chapter_number = 1  # Default to chapter 1 if we can't determine it
                
                # Try to determine the chapter number from the outline
                for i, outline_chapter in enumerate(outline.chapters_outline, 1):
                    if outline_chapter.title.lower() in chapter.chapter_title.lower() or chapter.chapter_title.lower() in outline_chapter.title.lower():
                        chapter_number = i
                        break
                
                # Write the chapter with proper formatting
                f.write(f"CHAPTER {chapter_number}\n")
                f.write(f"{chapter.chapter_title.upper()}\n")
                f.write("=" * len(chapter.chapter_title) + "\n\n")
                
                # Format the content with proper paragraphs
                # First, try to split by double newlines if they exist
                if '\n\n' in chapter.content:
                    paragraphs = chapter.content.split('\n\n')
                else:
                    # If no double newlines, split by periods followed by spaces to create paragraphs
                    sentences = chapter.content.split('. ')
                    paragraphs = []
                    current_paragraph = []
                    
                    for sentence in sentences:
                        current_paragraph.append(sentence)
                        if len(current_paragraph) >= 3:  # Group sentences into paragraphs (3 sentences per paragraph)
                            paragraphs.append('. '.join(current_paragraph) + ('.' if not current_paragraph[-1].endswith('.') else ''))
                            current_paragraph = []
                    
                    # Add any remaining sentences
                    if current_paragraph:
                        paragraphs.append('. '.join(current_paragraph) + ('.' if not current_paragraph[-1].endswith('.') else ''))
                
                # Write paragraphs with proper formatting
                for paragraph in paragraphs:
                    if paragraph.strip():
                        # Indent the first line of each paragraph
                        lines = paragraph.strip().split('\n')
                        if len(lines) > 0:
                            f.write("    " + lines[0] + "\n")
                            for line in lines[1:]:
                                f.write(line + "\n")
                            f.write("\n")  # Add an extra newline between paragraphs
            
            logger.info(f"Book chapter saved to {chapter_file}")
            print(f"✅ Book chapter saved to {chapter_file}")
        else:
            logger.warning("No chapter content was generated, nothing to save")
            print("⚠️ No chapter content was generated, nothing to save")

    except Exception as e:
        logger.error(f"Error in main function: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        print(f"ERROR: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())

