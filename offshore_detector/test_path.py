import os

print("Testing file paths:")
paths = [
    '/docs/offshore_countries.md',
    '/app/docs/offshore_countries.md',
    '../docs/offshore_countries.md',
    './docs/offshore_countries.md',
]

for path in paths:
    exists = os.path.exists(path)
    print(f"{path}: {'✅ EXISTS' if exists else '❌ NOT FOUND'}")
    if exists:
        with open(path) as f:
            lines = f.readlines()
            print(f"  - Lines: {len(lines)}")
            print(f"  - First line: {lines[0].strip()}")

print(f"\nCurrent working directory: {os.getcwd()}")
print(f"Directory contents of /: {os.listdir('/')}")
if os.path.exists('/app'):
    print(f"Directory contents of /app: {os.listdir('/app')}")
if os.path.exists('/docs'):
    print(f"Directory contents of /docs: {os.listdir('/docs')}")
