import urllib.request as req
from urllib.parse import urljoin # urljoin() function converts https://domain_name/page.html and /image/background.png in it
# to an url https://domain_name/image/background.png
from bs4 import BeautifulSoup
import cohere, numpy as np
from collections import deque
import time, os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv(dotenv_path = "./.env")
# There is module called render_template which is used to render html templates from templates directory directly.
# In Flask, each html page is called template. We can pass variables to thsi template by
# return render_template("<html_template_name.html", name="<value>") from route function
# This variable is then used in that html page as <body> ... {{name}} ... </body>

model = cohere.Client(os.getenv("CO_API_KEY"))

api = Flask(__name__) # Flask is the main class which takes module name as an argument. By locating module, Flask locates 
# the templates, static folders and all other related files.

CORS(api, origins=["http://localhost:3000"]) # Allowing Cross Origin Resource sharing particularly for this frontend

# In HTML's link tags, each tag's rel attribute can have multiple values seperated by spaces. Beautiful soup retuns it
# in form of list of strings for each attribute.

def visitLink(htmlCode, prompt, root):
    soup = BeautifulSoup(htmlCode, "lxml")
    try:
        text_embedding = model.embed(texts=[soup.body.get_text(separator = ' ', strip = True)],model="embed-english-v3.0",input_type="search_document").embeddings[0] # type: ignore
        prompt_embedding = model.embed(texts=[prompt],model="embed-english-v3.0",input_type="search_query").embeddings[0] # type: ignore
        arr1, arr2 = np.array(text_embedding), np.array(prompt_embedding)
        norm1, norm2 = np.linalg.norm(arr1), np.linalg.norm(arr2)
        similarity = float(np.dot(arr1, arr2) / (norm1 * norm2)) if norm1 and norm2 else 0.0
    except Exception as e:
        print("Embedding error:", e)
        return (0.0, [])
    childLinks = soup.find_all('a')
    title = soup.title.string if soup.title else "No title found"
# any() function can accept generator expressions other than interables.
    icoTag = soup.find(lambda tag : tag.name == "link" and tag.has_attr("rel") and any("icon" in relem.lower() for relem in tag["rel"]))
    icoUrl = urljoin(root, icoTag["href"]) if icoTag and icoTag.has_attr("href") else "blank" # type: ignore
# Here tag is an instance of bs4.element.Tag class which allows access to specific tag's attribute in dictinary format
    links = [urljoin(root, x["href"]) for x in childLinks if x.has_attr("href") and x["href"].startswith("http")] # type: ignore
    return (similarity, icoUrl, title, links)

#api.route is a decorator function that accepts any http requests specified in methods array, runs the underlined function, gets
# it's return value, converts it to http response and sends it back as response to client.
# Inner function of route decorator should have parameters when accessing route parameteres. Rest all are handled 
# using request object.
@api.route("/pagelinks", methods=["GET"])
def getList(): 
# request.args is a python dictionary, containing key, value pair where key is route query variable name and value is route query
# variable value.
    startNode, prompt, c = request.args["url"], request.args["search"], int(request.args["count"])
    linkList = {}
    q = deque()
    q.append(startNode)
    visited = set([startNode])
    i = 0
    while len(q) != 0 and i < c:
        root = q.popleft()
        try:
            with req.urlopen(root) as f:
                htmlCode = f.read().decode("utf-8", errors="ignore")
                similarity, icoUrl, title, links = visitLink(htmlCode, prompt, root) # type: ignore
                linkList[root] = (similarity, icoUrl, title)
                i += 1
                time.sleep(0.5)
        except Exception as e:
            print(f"Failed to open {root}: {e}")
            continue
        for link in links:
            if link not in visited and i < c:
                visited.add(link)
                q.append(link)
    sortedLinks = sorted(linkList.items(), key=lambda x: x[1][0], reverse=True) # For sorting dictionaries
# sorted returns a list of tuples where each tuple is a key value pair, because lonkList.items() returns so.
    return jsonify({"scrapLinks" : [{"url" : url, "icoSrc" : icoSrc, "ptitle" : ptitle} for url, (similarity, icoSrc, ptitle) in sortedLinks]})
# Can do jsonData = json.dumps({<Python dictionary}) and then return Response(jsonData, mimetype="application/json")
# It requires to import Response class from flask and json built in module. The above code is the most straightforward one,

if __name__ == "__main__":
    api.run(host = "0.0.0.0", port = 5001, debug = True)
# What do debug = True do?
#Enables the Debugger
#   -> If your app crashes, Flask shows a helpful debug web page with stack traces and interactive error inspection.
#Enables Auto-Reload (Code Reloading)
#   -> If you change your Python code and save the file, Flask automatically restarts the server.
#   -> This is similar to HMR behavior, but it's a full server restart, not true live reloading.

