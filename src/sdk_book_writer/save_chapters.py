import os

def save_book_outline(outline, output_dir="book_outputs"):
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, "outline.txt")
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("# BOOK OUTLINE\n\n")
        # Use 'outline.chapters' instead of 'outline.chapters_outline'
        for i, chapter in enumerate(outline.chapters, 1):  # Use 'chapters' here
            f.write(f"## Chapter {i}: {chapter.title}\n\n")
            f.write(f"{chapter.description}\n\n")
            if i < len(outline.chapters):
                f.write("---\n\n")
    print(f"\n✅ Book outline saved to {file_path}")


def save_book_chapter(book, output_dir="book_outputs"):
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, "chapter.txt")
    
    if book.chapters:
        chapter = book.chapters[0]
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"# {chapter.chapter_title}\n\n")
            f.write(chapter.content)
        print(f"\n✅ Book chapter saved to {file_path}")
    else:
        print("⚠️ No chapter content to save.")
