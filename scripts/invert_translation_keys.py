from bs4 import BeautifulSoup
import re

path_to_locale = "src/i18n"
locale_list = [
    "pt-BR",
    "fr",
    "ja",
    "es",
    "de",
    "it",
    "zh-CN",
    "zh-TW"
]
with open(f"{path_to_locale}/TSH_en.ts", "rt", encoding="utf-8") as english_file:
    english_text = english_file.read()
english_soup = BeautifulSoup(english_text, "xml")

locale_soup_dict = {}
for locale in locale_list:
    with open(f"{path_to_locale}/TSH_{locale}.ts", "rt", encoding="utf-8") as locale_file:
        locale_text = locale_file.read()
    locale_soup = BeautifulSoup(locale_text, "xml")
    locale_soup_dict[locale] = locale_soup

index = 0

for tag in english_soup.find_all("message"):
    source = tag.find_all("source")
    translation = tag.find_all("translation")
    old_source_text = source[0].text
    if "<html>" not in old_source_text and len(old_source_text)>1:
        parent = tag.parent
        new_source_text = f"TSH_legacy_{index:05}"
        detect_formats = re.findall(r"({[0-9]*})", old_source_text)
        if detect_formats:
            for string in detect_formats:
                new_source_text = new_source_text + f"_{string}"
        print(new_source_text, old_source_text)

        translation[0].string = old_source_text
        source[0].string = new_source_text

        locations = tag.find_all("location")
        for location in locations:
            file_path = location.get("filename")
            if file_path:
                file_path = file_path.replace("../", "src/")
                line_index = int(location.get("line")) - 1
                with open(file_path, "rt", encoding="utf-8") as code_file:
                    code_file_lines = code_file.readlines()
                    code_file_lines[line_index] = code_file_lines[line_index].replace(old_source_text, new_source_text)
                with open(file_path, "wt", encoding="utf-8") as code_file:
                    code_file.writelines(code_file_lines)
        
        for locale in locale_soup_dict.keys():
            locale_soup = locale_soup_dict[locale]
            locale_messages = locale_soup.find_all("message")
            for locale_message in locale_messages:
                locale_parent = locale_message.parent
                locale_source = locale_message.find_all("source")
                locale_context, context = locale_parent.find_all("name")[0].text, parent.find_all("name")[0].text
                if locale_context == context and locale_source[0].text == old_source_text:
                    locale_source[0].string = new_source_text
                    break
        
        if translation[0].get("type") == "unfinished" and old_source_text:
            del translation[0]["type"]



    index +=1

for locale in locale_soup_dict.keys():
    with open(f"{path_to_locale}/TSH_{locale}.ts", "wt", encoding="utf-8") as locale_file:
        locale_file.write(locale_soup_dict[locale].prettify())
    
with open(f"{path_to_locale}/TSH_en.ts", "wt", encoding="utf-8") as english_file:
    english_file.write(english_soup.prettify())
