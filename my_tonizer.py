import tiktoken

# Use the tokenizer associated with a model
encoding = tiktoken.encoding_for_model("gpt-4o")

text = "Hello, how are"

# Text → token IDs
tokens = encoding.encode(text)

print(tokens)
print("Number of tokens:", len(tokens))

# Token IDs → text
decoded = encoding.decode(tokens)

for token_id in tokens:
    token_str = encoding.decode([token_id])
    print(f"Token ID: {token_id}, Token String: '{token_str}'")

print(decoded)