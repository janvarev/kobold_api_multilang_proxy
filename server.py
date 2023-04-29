import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

path_settings_json =  "settings.json"
path_cache_en_json =  "cache_en.json"

import requests

version = "1.0"

params = {
    'port': 5020, # port for connect
    'is_advanced_translation': True, # usually always use advanced translation
    'kobold_url': "http://localhost:5001", # kobold API that we proxy
    'translator': 'GoogleTranslator', # GoogleTranslator or OneRingTranslator.
    'user_lang': '', # user language two-letters code like "fr", "es" etc.
    'custom_url': "http://127.0.0.1:4990/" # custom url for OneRingTranslator server
}

cache_en_translation:dict[str,str] = {"":"","<START>":"<START>"}
#en_not_translate:dict[str,str] = {}
def translator_main(string,from_lang:str,to_lang:str) -> str:
    from deep_translator import GoogleTranslator
    res = ""
    if params['translator'] == "GoogleTranslator":
        res = GoogleTranslator(source=from_lang, target=to_lang).translate(string)
    if params['translator'] == "OneRingTranslator":
        #print("GoogleTranslator using")
        #return GoogleTranslator(source=params['language string'], target='en').translate(string)
        custom_url = params['custom_url']
        if custom_url == "":
            res = "Please, setup custom_url for OneRingTranslator (usually http://127.0.0.1:4990/)"
        else:
            import requests
            response_orig = requests.get(f"{custom_url}translate", params={"text":string,"from_lang":from_lang,"to_lang":to_lang})
            if response_orig.status_code == 200:
                response = response_orig.json()
                #print("OneRingTranslator result:",response)

                if response.get("error") is not None:
                    print(response)
                    res = "ERROR: "+response.get("error")
                elif response.get("result") is not None:
                    res = response.get("result")
                else:
                    print(response)
                    res = "Unknown result from OneRingTranslator"
            elif response_orig.status_code == 404:
                res = "404 error: can't find endpoint"
            elif response_orig.status_code == 500:
                res = "500 error: OneRingTranslator server error"
            else:
                res = f"{response_orig.status_code} error"

    return res



class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/v1/model':

            self.send_response(200)
            self.end_headers()

            kobold_url = params.get("kobold_url")

            response_orig = requests.get(f"{kobold_url}/api/v1/model",
                                         params={})
            if response_orig.status_code == 200:

                self.wfile.write(response_orig.content)
            else:
                self.wfile.write("unknown_model_{0}_status_code".format(response_orig.status_code).encode("utf-8"))



        else:
            self.send_error(404)

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        body = json.loads(self.rfile.read(content_length).decode('utf-8'))
        kobold_url = params.get("kobold_url")

        if self.path == '/api/v1/generate':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()

            prompt = body['prompt']
            prompt_lines_orig = [k.strip() for k in prompt.split('\n')]
            import copy
            prompt_lines = copy.deepcopy(prompt_lines_orig)


            # running advanced translation logic
            if params["is_advanced_translation"]:

                stat_miss = 0
                for i in range(len(prompt_lines)):
                    if cache_en_translation.get(prompt_lines[i]) is not None:
                        print("CACHE en_translation hit:",prompt_lines[i])
                        prompt_lines[i] = cache_en_translation.get(prompt_lines[i])
                    else:
                        print("CACHE en_translation MISS!:", prompt_lines_orig[i])
                        stat_miss += 1
                        res = translator_main(prompt_lines_orig[i],params["user_lang"],"en")
                        cache_en_translation[prompt_lines_orig[i]] = res
                        prompt_lines[i] = res

                print("------ CACHE STAT: MISSES {0}/{1} (lower - better, ideally - 1)".format(stat_miss,len(prompt_lines)))





            #res = generate_reply(prompt, generate_params, stopping_strings=stopping_strings)
            import copy
            body_copy = copy.deepcopy(body)
            body_copy['prompt'] = "\n".join(prompt_lines)

            print("Request to Kobold:",body_copy)

            response = requests.post(f"{kobold_url}/api/v1/generate", json=body_copy).json()

            # seems we need it here....
            #answer = answer[len(prompt):]
            answer = response["results"][0]['text']


            if params["is_advanced_translation"]:
                print("is_advanced_translation original answer:", answer )
                answer_lines_orig = [k.strip() for k in answer.split('\n')]
                answer_lines = copy.deepcopy(answer_lines_orig)
                for i in range(len(answer_lines)):
                    res = translator_main(answer_lines_orig[i],"en",params["user_lang"])
                    cache_en_translation[res] = answer_lines_orig[i]
                    answer_lines[i] = res

                # special case - mixing two end phrases together

                # example: prompt end: Aqua:
                # result end: Hi!
                # so we need cache for phrase "Aqua: Hi!"

                complex_phrase1_user = prompt_lines_orig[len(prompt_lines_orig)-1]+" "+answer_lines[0]
                complex_phrase1_user2 = prompt_lines_orig[len(prompt_lines_orig) - 1] + answer_lines[0]
                complex_phrase1_en = prompt_lines[len(prompt_lines_orig)-1]+" "+answer_lines_orig[0]
                cache_en_translation[complex_phrase1_user] = complex_phrase1_en
                cache_en_translation[complex_phrase1_user2] = complex_phrase1_en

                answer = "\n".join(answer_lines)

                print("is_advanced_translation final answer:", answer)

                save_cache_en()

            response = json.dumps({
                'results': [{
                    'text': answer
                }]
            })
            self.wfile.write(response.encode('utf-8'))
        else:
            self.send_error(404)


def run_server(is_listen:bool = False, is_share:bool = False):
    server_addr = ('0.0.0.0' if is_listen else '127.0.0.1', params['port'])
    server = ThreadingHTTPServer(server_addr, Handler)
    if is_share:
        try:
            from flask_cloudflared import _run_cloudflared
            public_url = _run_cloudflared(params['port'], params['port'] + 1)
            print(f'Starting KoboldAI api translation proxy at {public_url}/api')
        except ImportError:
            print('You should install flask_cloudflared manually')
    else:
        print(f'Starting KoboldAI api translation proxy at http://{server_addr[0]}:{server_addr[1]}/api')
        server.serve_forever()


def setup():
    load_settings()
    if params["user_lang"] == "":
        params["user_lang"] = input("What's your native language? (enter 2-code symbols, like 'en','fr','es'):")
    save_settings()
    load_cache_en()
    print("Loaded Cache_en length: {0}".format(len(cache_en_translation)))
    #Thread(target=run_server, daemon=True).start()
    run_server()


# settings etc
def save_settings():
    global params


    with open(path_settings_json, 'w') as f:
        json.dump(params, f, indent=2)

def save_cache_en():
    global cache_en_translation

    with open(path_cache_en_json, 'w', encoding="utf-8") as f:
        json.dump(cache_en_translation, f, indent=2)

def load_settings():
    global params

    try:
        with open(path_settings_json, 'r') as f:
            # Load the JSON data from the file into a Python dictionary
            data = json.load(f)

        if data:
            params = {**params, **data} # mix them, this allow to add new params seamlessly

    except FileNotFoundError:
        #memory_settings = {"position": "Before Context"}
        save_settings()
        pass

def load_cache_en():
    global cache_en_translation

    try:
        with open(path_cache_en_json, 'r') as f:
            # Load the JSON data from the file into a Python dictionary
            data = json.load(f)

        if data:
            cache_en_translation = {**cache_en_translation, **data} # mix them, this allow to add new params seamlessly

    except FileNotFoundError:
        #memory_settings = {"position": "Before Context"}
        pass


if __name__ == "__main__":
    print("Running kobold_api_multilang_proxy server v{0}...".format(version))
    setup()