# Tool to deal with high-cardinality columns:
import ast
import re
from langchain_community.vectorstores.faiss import FAISS
from langchain.agents.agent_toolkits import create_retriever_tool
from langchain_openai import OpenAIEmbeddings
from langchain_community.utilities import SQLDatabase


# Import courses database
db = SQLDatabase.from_uri("sqlite:///data/courses.db", max_string_length=3000) # max_string_length ensures full course description is returned

# Function that parses the result of query into a list of elements
def query_as_list(db, query):
    res = db.run(query)
    res = [el for sub in ast.literal_eval(res) for el in sub if el]
    res = [re.sub(r"\b\d+\b", "", string).strip() for string in res]
    return list(set(res))

##Create list of class names and teacher names
classeNames = query_as_list(db, "SELECT Title FROM courses")
teacherNames = query_as_list(db, "SELECT Instructor FROM courses")

# Create a retriever tool that the agent can execute at its discretion:
## Embed results in vector database
vector_db = FAISS.from_texts(classeNames + teacherNames, OpenAIEmbeddings())

## Create and define retriever tool
retriever = vector_db.as_retriever(search_kwargs={"k": 5})
description = """Use to look up values to filter on. Input is an approximate spelling of the proper noun, output is \
valid proper nouns. Use the noun most similar to the search."""
proper_nouns_tool = create_retriever_tool(
    retriever,
    name="search_proper_nouns",
    description=description,
)