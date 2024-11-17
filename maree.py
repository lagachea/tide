import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
from io import StringIO
import locale

locale.setlocale(locale.LC_ALL, 'fr_FR')
# Définir les dates
start_date = datetime(2025, 1, 1)
end_date = datetime(2025, 12, 31)
delta = timedelta(days=1)

with open("cookie.txt", "r") as cookietxt:
    cookie = cookietxt.read()[:-1]

# Set headers manually
headers = {
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Cookie": cookie,
}

# Initialiser la liste des données
parse = []
final_dataframe = pd.DataFrame()

# Boucle sur chaque jour de l'année
current_date = start_date
while current_date <= end_date:
    # Récupérer la page web pour le jour actuel (URL et méthode d'accès à ajuster selon le site)
    url = f"https://maree.info/150?d={current_date.strftime('%Y%m%d')}"

    response = requests.get(url, headers=headers)

    soup = BeautifulSoup(response.content, "html.parser")


    for tide in soup.find_all(id="MareeJours"):
        string_table = StringIO(str(tide))
        dataframe = pd.read_html(string_table)[0]

    # handle Changement d heure (ignore la ligne)
    if len(dataframe.values) > 7:
        dataframe.drop(
            dataframe[dataframe["Date"].str.contains("Changement") == True].index,
            inplace=True,
        )

    # iter on rows of week
    for row in dataframe.iterrows():
        values = row[1].to_numpy()
        _, hours, heights, coefficients = values
        date = current_date.strftime("%A %d %B %Y")
        # print(date)

        heights = heights.split(" ")
        hours = hours.split(" ")
        coefficients = list(filter(lambda x: len(x) > 0, coefficients.split(" ")))

        # print(heights)
        number_heigts = list(map(lambda x: float(x[:-1].replace(",", ".")), heights))
        if number_heigts[0] > number_heigts[1]:
            # high tide first
            coefficients.insert(1, "")
            coefficients.insert(3, "")
        else:
            # high tide second
            coefficients.insert(0, "")
            coefficients.insert(2, "")

        days = []
        for hour, height, coefficient in zip(hours, heights, coefficients):
            day = (date, hour, height, coefficient)
            days.append(day)

        # drop low tides
        days = list(filter(lambda x: x[3] != "",days))

        parse.extend(days)
        current_date += delta
    print(current_date)


# Exporter vers Excel
df = pd.DataFrame(parse, columns=["date", "heure", "hauteur", "coefficient"])
# print(df)

# some room to test "heure" to remove at night
# some room to test "coefficient" to compute "heure de sortie"
df.to_excel("marees_le_crotoy_2025.xlsx", index=False)
