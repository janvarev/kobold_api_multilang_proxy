# Kobold API Proxy translation server

Allow you to use KoboldAI API on your UserLanguage.

**Provide advanced logic to auto-translate income prompts:**
- Due to advanced logic script splits income prompt by lines, and cache translation results
 

Features:
- **Text quality feature:** when it generate English response, it cache it too (so you don't do double-translation English->UserLang->English next time)
- **Multi translation engines**. You can setup your own translator, if you want (throw OneRingTranslator option) 

## One-click installer for Windows

to be done

## Install and run

To run: 
1. Install requirements ```pip install -r requirements.txt```
2. Run server.py.

## Core settings description

Located in `settings.json` after first run.

```python
{
  "port": 5020, # port for
  "is_advanced_translation": true,
  "kobold_url": "http://localhost:5001",
  "translator": "GoogleTranslator",
  "user_lang": "ru"
},
```

## API example usage

Translate from en to fr
```
http://127.0.0.1:4990/translate?text=Hi%21&from_lang=en&to_lang=fr
```

Translate from en to user language (user language defines in plugins/core.json)
```
http://127.0.0.1:4990/translate?text=Hi%21&from_lang=en&to_lang=user
```

Full Python usage example:
```python
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
```
