import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
from io import StringIO
import locale
import json

locale.setlocale(locale.LC_ALL, "fr_FR")
# Définir les dates
start_date = datetime(2025, 1, 1)
end_date = datetime(2025, 12, 31)
delta = timedelta(days=1)


def get_sun_times(start, end):
    gps_lat = "50.216569"
    gps_lng = "1.624047"
    timezone = "CET"
    params = {
        "lat": gps_lat,
        "lng": gps_lng,
        "timezone": timezone,
        "date_start": start_date.strftime("%Y-%m-%d"),
        "date_end": end_date.strftime("%Y-%m-%d"),
        "time_format": "24",
    }

    # get the sunrise and sunset time
    timeurl = "https://api.sunrisesunset.io/json"
    response = requests.get(timeurl, params=params)
    res = json.loads(response.content)
    return res["results"]


sun_times = get_sun_times(start_date, end_date)

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
tide_dics = []

# Boucle sur chaque jour de l'année
current_date = start_date
while current_date <= end_date:
    # Récupérer la page web pour le jour actuel (URL et méthode d'accès à ajuster selon le site)
    tide_params = {"d": current_date.strftime("%Y%m%d")}
    tide_url = "https://maree.info/150"
    response = requests.get(tide_url, headers=headers, params=tide_params)

    soup = BeautifulSoup(response.content, "html.parser")

    for tide in soup.find_all(id="MareeJours"):
        string_table = StringIO(str(tide))
        df_html_table = pd.read_html(string_table)[0]

    # handle Changement d heure (ignore la ligne)
    if len(df_html_table.values) > 7:
        df_html_table.drop(
            df_html_table[df_html_table["Date"].str.contains("Changement")].index,
            inplace=True,
        )

    # iter on rows of week
    for row, sun_time in zip(df_html_table.iterrows(), sun_times):
        date = current_date.strftime("%A %d %B %Y")
        # as df_html_table is 7 days, it can oveshoot by up to 6 days
        if current_date > end_date:
            break

        values = row[1].to_numpy()
        _, hours, heights, coefficients = values
        # print(date)

        heights = heights.split(" ")
        hours = hours.replace("h", ":").split(" ")
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

        sunrise, sunset = sun_time["sunrise"][:-3], sun_time["sunset"][:-3]
        # print(sunrise, sunset)

        day = []
        for hour, height, coefficient in zip(hours, heights, coefficients):
            # add sunrise and sunset time
            # tide = (date, hour, height, coefficient, sunrise, sunset)
            tide = {
                "date": date,
                "heure": hour,
                "hauteur": height,
                "coefficient": coefficient,
                "lever du soleil": sunrise,
                "coucher du soleil": sunset,
            }
            day.append(tide)

        # drop low tides
        day = list(filter(lambda x: x["coefficient"] != "", day))

        tide_dics.extend(day)
        current_date += delta
    # remove the 7 first elements consumed by last loop
    sun_times = sun_times[6:]
    print(current_date)


# Exporter vers Excel
df = pd.DataFrame(tide_dics)
# print(df)


def get_minutes_from_time(time):
    hours = int(time[:2])
    minutes = int(time[-2:])
    return 60 * hours + minutes


def get_modified_time(time, modif):
    total = get_minutes_from_time(time) + modif
    hours = total // 60
    minutes = total % 60
    return f"{hours:02}:{minutes:02}"


def hour_by_coeff(row):
    coefficient = int(row["coefficient"])
    hour = row["heure"]
    if coefficient > 0 and coefficient <= 40:
        return get_modified_time(hour, -30)
    elif coefficient > 40 and coefficient <= 60:
        return get_modified_time(hour, -15)
    elif coefficient > 60 and coefficient < 80:
        return get_modified_time(hour, 0)
    elif coefficient >= 80 and coefficient < 90:
        return get_modified_time(hour, 15)
    elif coefficient >= 90 and coefficient < 100:
        return get_modified_time(hour, 30)
    elif coefficient >= 100 and coefficient < 110:
        return get_modified_time(hour, 45)
    elif coefficient >= 110:
        return get_modified_time(hour, 60)
    else:
        return "ERROR could not compute hour"


def is_night_hour(row):
    # heure de sortie>=lever du soleil - TIME(0;15;0)
    # and
    # heure de sortie<=coucher du soleil - TIME(0;45;0)
    # "OK"; "NUIT"
    sunrise = get_minutes_from_time(row["lever du soleil"])
    sunset = get_minutes_from_time(row["coucher du soleil"])
    sortie = get_minutes_from_time(row["heure de sortie"])

    if sortie >= sunrise - 15 and sortie <= sunset - 45:
        return row["heure de sortie"]
    else:
        return "NUIT"


df["heure de sortie"] = df.apply(hour_by_coeff, axis=1)
df["heure de sortie"] = df.apply(is_night_hour, axis=1)


df.to_excel("marees_le_crotoy_2025.xlsx", index=False)
