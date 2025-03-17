import pickle
import os
from operator import itemgetter
from langchain.prompts import PromptTemplate
from langchain.text_splitter import MarkdownTextSplitter
from langchain_community.document_loaders import ToMarkdownLoader
from langchain_core.output_parsers import StrOutputParser
from langchain_community.vectorstores import DocArrayInMemorySearch
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from dotenv import load_dotenv
from langchain.tools import tool

# Load API keys from .env
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
markdown_api_key = os.getenv("2MARKDOWN_API_KEY")

# Function to load/scrape Gtown COSC bulletin and split the content (using markdown language)
def load_or_scrape_content(file_path):
    # If file exists:
    if os.path.exists(file_path):
        with open(file_path, 'rb') as file:
            documents = pickle.load(file)
            print("Loaded cosc bulletin content from pkl file.")
            return documents

    # Else, scrape the website:
    print("File not found. Scraping website...")
    text_splitter = MarkdownTextSplitter(
        chunk_size=2000,
        chunk_overlap=200 
    )
    loader = ToMarkdownLoader(
        "https://bulletin.georgetown.edu/schools-programs/college/degree-programs/computer-science/",
        api_key=markdown_api_key
    )
    documents = loader.load_and_split(text_splitter)

    # Save to file
    with open(file_path, 'wb') as file:
        pickle.dump(documents, file)
        print("Content saved to file.")

    return documents

# Load or scrape the content
file_path = "./data/georgetown_coscs_bulletin.pkl"
documents = load_or_scrape_content(file_path)

# Load the content into a vector store
vectorstore = DocArrayInMemorySearch.from_documents(
    documents, embedding=OpenAIEmbeddings()
)

# Configure retriever with specific parameters
retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={
        "k": 3,  # Number of relevant chunks to return
        "score_threshold": 0.7,  # Only return results above this similarity score
        "fetch_k": 5  # Fetch more candidates than k for better filtering
    }
)

# Prepare the prompt template
template = """
Find the most relevant portions of the context that directly address this question: {question}

Consider:
- Specific course requirements or prerequisites
- Program policies or regulations
- Relevant degree requirements
- Related course offerings

Context: {context}

Return only the most pertinent excerpts, preserving exact numbers, course codes, and requirements. 
Exclude any irrelevant or redundant information.
"""
prompt = PromptTemplate.from_template(template)

model = ChatOpenAI(openai_api_key=openai_api_key, model="gpt-4o-mini")  # Can use a smaller model
parser = StrOutputParser()

chain = (
    {
        "context": itemgetter("question") | retriever,
        "question": itemgetter("question"),
    }
    | prompt
    | model
    | parser
)

@tool
def cosc_expert_tool(query: str) -> str:
    """Tool for retrieving relevant context about the COSC program from the Georgetown bulletin.
    Returns precise excerpts about course requirements, prerequisites, and program policies."""
    result = chain.invoke({"question": query})
    return result