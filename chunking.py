import bs4 as bs
import urllib.request
from course import Course
from constants import WEBSOC
import time


def get_chunks_for(course_codes: [str], all_course_codes: [[str]]) -> [[str]]:
    """
        Creates an optimized list of chunks to perform a search with given a list of course codes and chunks
    """
    course_codes = sorted(course_codes)
    code_index_map = dict()

    for i in range(len(all_course_codes)):
        code_index_map[all_course_codes[i]] = i

    final_chunks = []
    current_chunk = []

    for code in course_codes:
        if len(current_chunk) == 0:
            current_chunk.append(code)
        else:
            first_code = current_chunk[0]

            if int(code_index_map[code]) - int(code_index_map[first_code]) < 900:
                current_chunk.append(code)
            else:
                final_chunks.append(current_chunk)
                current_chunk = [code]

    if len(current_chunk) != 0:
        final_chunks.append(current_chunk)

    batched_chunks = []
    current_batch = []

    for chunk in final_chunks:
        if len(current_batch) + len(chunk) <= 8:
            current_batch.extend(chunk)
        else:
            batched_chunks.append(chunk)

        if len(current_batch) == 8:
            batched_chunks.append(current_batch)
            current_batch = []

    if len(current_batch) != 0:
        batched_chunks.append(current_batch)

    return batched_chunks


def get_chunks(term) -> [[str]]:
    course_codes = sorted(get_all_codes(term))

    chunks = []
    inner_list = []
    counter = 0

    for code in course_codes:
        inner_list.append(code)
        counter += 1

        if counter == 900:
            counter = 0
            chunks.append(inner_list)
            inner_list = []

    if len(inner_list) != 0:
        chunks.append(inner_list)

    return chunks


def _get_courses_in_page(url) -> [Course]:
    """
        Given a WebSoc search URL, creates a generator over each Course in the results page
    """

    # Get the page that lists the courses in a table
    with urllib.request.urlopen(url) as source:
        soup = bs.BeautifulSoup(source, "html.parser")

    # Iterate over each course, which is each row in the results
    for row in soup.find_all("tr"):
        # Get the values of each column
        cells = [td.string for td in row.find_all("td")]

        # Convert this row to a Course object
        if len(cells) in {15, 16, 17}:
            yield Course(cells)


def _get_department_urls(term) -> [str]:
    """
        Creates a generator over the URLs of each department's WebSOC search results page
    """

    # Get the page that lists all the departments
    with urllib.request.urlopen(WEBSOC) as source:
        soup = bs.BeautifulSoup(source, "html.parser")

    # Extract the department codes from the department menu
    for deptOption in soup.find("select", {"name": "Dept"}).find_all("option"):
        url_fields = [("YearTerm", term),
                      ("ShowFinals", '1'),
                      ("ShowComments", '1'),
                      ("Dept", deptOption.get("value")),
                      ("CancelledCourses", 'Include')]

        # Encode the URL that shows courses in this department
        yield f'{WEBSOC}?{urllib.parse.urlencode(url_fields)}'


def get_all_codes(term) -> [str]:
    """
        Generates all of the codes currently on WebSoc
    """

    codes = []

    for url in _get_department_urls(term):
        time.sleep(1)
        for course in _get_courses_in_page(url):
            codes.append(course.code)

    return codes
