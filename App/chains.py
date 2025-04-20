import os
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.exceptions import OutputParserException
from dotenv import load_dotenv

load_dotenv()

class Chain:
    def __init__(self):
        self.llm = ChatGroq(temperature=0.7, groq_api_key=os.getenv("GROQ_API_KEY"), model_name="llama-3.3-70b-versatile")

    def extract_jobs(self, cleaned_text):
        prompt_extract = PromptTemplate.from_template(
            """
            ### SCRAPED TEXT FROM WEBSITE:
            {page_data}
            ### INSTRUCTION:
            The scraped text is from the career's page of a website.
            Your job is to extract the job postings and return them in JSON format containing the following keys: `role`, `experience`, `skills` and `description`.
            Only return the valid JSON.
            ### VALID JSON (NO PREAMBLE):
            """
        )
        chain_extract = prompt_extract | self.llm
        res = chain_extract.invoke(input={"page_data": cleaned_text})
        try:
            json_parser = JsonOutputParser()
            res = json_parser.parse(res.content)
        except OutputParserException:
            raise OutputParserException("Context too big. Unable to parse jobs.")
        return res if isinstance(res, list) else [res]

    def write_mail(self, job, links):
        prompt_email = PromptTemplate.from_template(
            """
            ### JOB DESCRIPTION:
            {job_description}

            ### INSTRUCTION:
            Okay, here is a prompt for your cold email generator project, based on the information in your CV  and the structure of the example you provided:   

Prompt:

You are Sumit Tiwari, a motivated and results-oriented individual with a strong foundation in computer science principles and expertise in C/C++, AI/ML, and web development. You have proven experience in developing innovative web applications, such as a personal portfolio site  and a resume-building tool ('craft.resume'), demonstrating skills in HTML, CSS, JavaScript, and potentially frameworks like ReactJS or Node.js (listed under technical skills). You also have experience leading teams and coordinating technical projects, as shown in your role as Management Lead at GDG MITS-DU.   

Your job is to write a cold email to a potential client or recruiter regarding an opportunity (e.g., freelance project, job opening) that aligns with your skills. The email should highlight your capabilities in areas like:

Full-stack web development
Creating user-centric web applications  
Front-end technologies (HTML, CSS, JS)  
Project coordination and leadership  
Problem-solving (evidenced by DSA problem-solving )
**Write a professional and concise cold email to [Company Name] regarding the job mentioned above describing the capability of Sumit  
in fulfilling their needs at job role [Job Title/General Area of Interest] opportunities.
** 

In your email:

1. **Highlight your key skills:** Emphasize your proficiency in full-stack development, DSA, and any relevant coursework or projects.
2. **Showcase your academic background:** Briefly mention your B.Tech in Mathematics and Computing from MITs Gwalior.
3. **Express your enthusiasm:** Convey your eagerness to learn and contribute to a growing company.
4. **Include a clear call to action:** Request an opportunity to discuss your qualifications further through an interview or informational meeting.

**Keep the email concise, professional, and impactful. Tailor your message to resonate with the specific company and its values.**

**Optional:**

* If you have a personal website or online portfolio, like this is my protfolio link(https://mesumittiwari.github.io/My-WebPage/), and my email is: sumittiwari2414@gmail.com, include a link in your email signature.
* Quantify your achievements whenever possible (e.g., "Completed [Number] projects", "Achieved [Rank] in [Coding Competition]").



**Remember to:**

* Replace the bracketed information with your specific details.
* Research the company and tailor your email to their specific values and culture.
* Proofread carefully for any grammatical or spelling errors.
### EMAIL (NO PREAMBLE):
"""
        )
        chain_email = prompt_email | self.llm
        res = chain_email.invoke({"job_description": str(job), "link_list": links})
        return res.content

if __name__ == "__main__":
    print(os.getenv("GROQ_API_KEY"))