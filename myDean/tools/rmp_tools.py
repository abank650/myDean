import requests
from bs4 import BeautifulSoup
from langchain.tools import tool

georgetown = 355

def get_professor_id(professor_name, school_id):
    # Construct the search URL
    search_url = f"https://www.ratemyprofessors.com/search/professors/{school_id}?q={professor_name}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # Make the request
    response = requests.get(search_url, headers=headers)
    if response.status_code != 200:
        return f"Failed to fetch data from {search_url}. Status code: {response.status_code}"
    
    # Parse the HTML content
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Look for the professor link in the search results
    professor_element = soup.select_one('a.TeacherCard__StyledTeacherCard-syjs0d-0')
    if professor_element:
        # Extract the href attribute to get the professor's ID
        professor_url = professor_element['href']
        professor_id = professor_url.split('/')[-1]  # Extract the last part of the URL as the ID
        return professor_id
    else:
        return "Professor not found."
    
def scrape_professor_data(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return f"Failed to fetch data from {url}. Status code: {response.status_code}"
    
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Extract professor's name
    name_element = soup.select_one('h1.NameTitle__NameWrapper-dowf0z-2.erLzyk')
    professor_name = name_element.text.strip() if name_element else "N/A"
    
    # Extract department
    department_element = soup.select_one('b')
    department = department_element.text.strip() if department_element else "N/A"
    
    # Extract rating
    rating_element = soup.select_one('div.RatingValue__Numerator-qw8sqy-2.liyUjw')
    rating = rating_element.text.strip() if rating_element else "N/A"
    
    # Extract difficulty
    difficulty_element = soup.find('div', string="Level of Difficulty").find_previous_sibling('div')
    difficulty = difficulty_element.text.strip() if difficulty_element else "N/A"

    # Extract "Would Take Again" percentage
    take_again_element = soup.select('div.FeedbackItem__FeedbackNumber-uof32n-1.kkESWs')
    would_take_again = take_again_element[0].text.strip() if take_again_element else "N/A"

    # Extract number of reviews
    num_reviews_element = soup.select_one('li.TeacherRatingTabs__StyledTab-pnmswv-2')
    num_reviews = num_reviews_element.text.split()[0] if num_reviews_element else "N/A"


    # Format the output
    output = f"Name: {professor_name}\n"
    output += f"Department: {department}\n"
    output += f"Rating: {rating} / 5.0\n"
    output += f"Difficulty: {difficulty} / 5.0\n"
    output += "Total Ratings: %s\n" % num_reviews
    output += f"Would Take Again: {would_take_again}"
    
    return output

def scrape_professor_reviews(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return f"Failed to fetch data from {url}. Status code: {response.status_code}"
    
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Extract reviews
    reviews = []
    review_elements = soup.select('div.Rating__RatingBody-sc-1rhvpxz-0.dGrvXb')
    for review in review_elements[:5]:  # Extract only the first 5 reviews
        comment_element = review.select_one('div.Comments__StyledComments-dzzyvm-0.gRjWel')
        comment = comment_element.text.strip() if comment_element else "No comment"
        reviews.append(comment)
    output = "Recent Reviews:\n" + "\n".join(reviews)

    return output

# Define the rmp_tool to return information about professor
@tool
def rmp_tool(professor_name):
    """Tool for retrieving information about professors."""

    professor = get_professor_id(professor_name, georgetown)
    if professor is None:
        return f"no ratings found on Rate my Professor for {professor_name}"
    else:
        url = f"https://www.ratemyprofessors.com/professor/{professor}"
        return scrape_professor_data(url)

@tool
def rmp_reviews_tool(professor_name):
    """Tool for retrieving detailed reviews about a Georgetown professor.
    
    Args:
        professor_name (str): The full name of the professor to search for
        
    Returns:
        str: Detailed reviews and comments from students about the professor
    """
    professor = get_professor_id(professor_name, georgetown)
    if professor is None:
        return f"no ratings found on Rate my Professor for {professor_name}"
    else:
        url = f"https://www.ratemyprofessors.com/professor/{professor}"
        return scrape_professor_reviews(url)