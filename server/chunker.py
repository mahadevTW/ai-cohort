from fileinput import filename
import os
import json
from openai_client import openai_chunker

# '''system_messages = I want to write a chunker.py file 
# It will get a directory as file path C:\AI_Learning\git\ai-cohort\data\policies to chunker function 
# all file present in directory are plane text files (*.ml). Files will be having filename as actual file name, section and sub-section and content as it's data.
# It should read the file contents and pass it to a function openai_chunker
# '''

directory_path_tst = r"C:\AI_Learning\git\ai-cohort\data\policies"
filename_tst = "01-onboarding-policy.md"  # Replace with the actual filename you want to process

def chunker(directory_path,filename:str):
    chunks = []
    if filename.endswith(".md"):
        file_path = os.path.join(directory_path, filename)
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()
            # Call the openai_chunker function with the content of the file
            print(f"Before Processing file: {filename}")
            generated_chunks = openai_chunker(filename=filename, content=content)
            chunks.extend(generated_chunks)
            print(f"Processed file: {filename}, generated {len(generated_chunks)} chunks.")
    return chunks

if __name__ == "__main__":
    # Example usage
    all_chunks = chunker(directory_path_tst, filename_tst)
    print(f"Total chunks generated: {len(all_chunks)}") 