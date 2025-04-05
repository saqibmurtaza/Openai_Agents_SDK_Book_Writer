from agents import (
    Agent, 
    OpenAIChatCompletionsModel, 
    Runner, 
    set_tracing_disabled,
    set_default_openai_api,
    set_default_openai_client
    )
from agents.run import RunConfig
from openai import AsyncOpenAI
from dotenv import load_dotenv
from sdk_book_writer.model import BookOutline, Book
from sdk_book_writer.tool import search_tool
import os, asyncio

set_tracing_disabled(True)

load_dotenv()

BASE_URL= os.getenv('BASE_URL') or ""
API_KEY= os.getenv('API_KEY') or ""
MODEL_NAME= os.getenv('MODEL_NAME') or ""

if not BASE_URL or not API_KEY or not MODEL_NAME:
    raise ValueError(
        "Please set EXAMPLE_BASE_URL, EXAMPLE_API_KEY, EXAMPLE_MODEL_NAME via env var or code."
    )

"""This example uses a custom provider for all requests by default. We do three 
things:
1. Create a custom client.
2. Set it as the default OpenAI client, and don't use it for tracing.
3. Set the default API as Chat Completions, as most LLM providers don't yet 
support Responses API.

Note that in this example, we disable tracing under the assumption that you don't 
have an API key from platform.openai.com. If you do have one, you can either 
set the `OPENAI_API_KEY` env var or call set_tracing_export_api_key() to 
set a tracing specific key.
"""

client= AsyncOpenAI(
    base_url=BASE_URL,
    api_key=API_KEY,
)

set_default_openai_client(client=client, use_for_tracing=False)
set_default_openai_api("chat_completions")
set_tracing_disabled(disabled=True)


generate_book_outline= Agent(
    name="Book Writer",
    handoff_description = "Specialist agent for researching topics and gathering " \
    "high-quality information to support course outline creation",
    instructions = """
    You are a research assistant tasked with gathering essential information 
    for creating a high-quality course outline.

    You can:
    1. Research the provided topic thoroughly
    2. Focus on collecting the most important and relevant information
    3. Use only high-quality, reliable sources

    Always be accurate, detail-oriented, and aligned with the author's goals 
    for the course. Provide information that will support a clear and 
    engaging course structure.

    When conducting research, consider:
    - The core concepts and learning objectives of the topic
    - The target audience and their level of expertise
    - The intended outcome of the course
    - The reliability and credibility of all sources

    Ensure that all research is grounded in trustworthy references, and avoid 
    low-quality or unverified content.
    Strict Requirement: Do **not** include any additional fields in your response, 
    such as "metadata", "store", or any other unrecognized keys. 
    Only use fields that are explicitly defined in the expected schema.
    """,
    model=MODEL_NAME,
    tools=[search_tool],
    output_type=BookOutline
    )

write_book = Agent(
    name="Book_writer",
    instructions="""
    You are a creative and detail-oriented book writing assistant who helps 
    users turn their ideas into engaging, well-written content.

    You can:
    1. Choose one chapter from the provided book outline
    2. Write high-quality, in-depth content for that chapter only
    3. Maintain a consistent tone and narrative style appropriate for the book

    Always be thoughtful, clear, and aligned with the user’s vision for the book. 
    Focus on depth and quality rather than covering all chapters at once.

    When writing the chapter, consider:
    - The target audience and their level of understanding
    - The structure and goals of the overall book
    - The tone, style, and voice that fits the topic
    - Adding detail, examples, and insights that bring the content to life

    Important: Select one chapter from the outline that you believe is impactful 
    or foundational. Do **not** attempt to write the full book or 
    multiple chapters in one go, to avoid exhausting resources.

    If the outline is incomplete or unclear, hand off to the book outline generation 
    agent for support.
    Strict Requirement: Do **not** include any additional fields in your response, 
    such as "metadata", "store", or any other unrecognized keys. 
    Only use fields that are explicitly defined in the expected schema.
    """,
    model=MODEL_NAME,
    tools=[search_tool],
    handoffs=[generate_book_outline],
    output_type=Book
)

async def main():
    # Single book topic for the full flow
    query = "Write a book on 'Mindfulness for Busy Professionals'"
    
    print("\n" + "=" * 60)
    print(f"QUERY: {query}")
    
    # Step 1: Generate the outline
    outline_result = await Runner.run(generate_book_outline, query)
    outline = outline_result.final_output
    print(f" FINAL OUTLINE RESULTS : { outline_result}")
    print(f" FINAL OUTPUT : { outline}")
    
    print("\n🧭 BOOK OUTLINE:\n")
    for i, chapter in enumerate(outline.chapters_outline, 1):
        print(f"{i}. {chapter.title}")
        print(f"   📄 {chapter.description}\n")
    
    # Step 2: Write one chapter based on the outline
    write_input = outline  # Pass the full BookOutline to the write_book agent
    book_result = await Runner.run(write_book, write_input)
    book = book_result.final_output
    
    # Print the written chapter
    print("\n📝 WRITTEN CHAPTER:\n")
    if book.chapters:
        chapter = book.chapters[0]
        print(f"📎 Chapter Title: {chapter.chapter_title}\n")
        print(chapter.content)
    else:
        print("⚠️ No chapter content was generated.")

if __name__ == "__main__":
    asyncio.run(main())

