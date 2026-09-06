import os

from server.openai_client import chunk_string

def chunk_all_documents(base_directory:str):
    # iterate over the directory and for every file, read the file content, make llm call to brerakdown file into chunks based on index available in the file itself
    # for each file llm should return list of chunks, each chunk has below fields
    #  file_title which is name of file, section is mentioned in the file, subsection and chunk_data which is data inside that suyb section
    all_chunks = []
    for file_name in os.listdir(base_directory):
        file_path = os.path.join(base_directory, file_name)
        if not os.path.isfile(file_path):
            continue
        if "01-onboarding-policy.md" not in file_path:
            print(f"ignoring the file {file_path}")
            continue
        with open(file_path, "r", encoding="utf-8") as file:
            print(f"chunking for the file  {file}")
            content = file.read()
            result = chunk_string(content, file_name)
            print(result)
            all_chunks.extend(result)
    return all_chunks

if __name__ == "__main__":
    base_directory = "./data/policies"
    chunk_all_documents(base_directory)