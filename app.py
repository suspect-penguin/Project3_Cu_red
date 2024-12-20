from flask import Flask, request, render_template, redirect, url_for
import requests
import csv
import dash
from dash import dcc, html
import pandas as pd
import plotly.graph_objs as go

# Создаем экземпляры Flask и Dash приложения
app = Flask(__name__)  # Flask используется для обработки основной веб-страницы
dash_app = dash.Dash(__name__, server=app, url_base_pathname='/dashboard/')  # Dash используется для отображения графиков
dash_app.layout = html.Div()  # Изначально layout пуст, будет заполняться данными позже


API_KEY = ''
BASE_URL = 'http://dataservice.accuweather.com'

# Функция для сохранения полученных данных о погоде в CSV файл
def save_weather_data_to_csv(weather_data_list, csv_file_path, city_names):
    headers = ['City', 'Date', 'Average Temperature', 'Wind Speed', 'Precipitation Probability', 'Condition']

    # Открытие CSV файла для записи
    with open(csv_file_path, mode='w', newline='', encoding='utf-8') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=headers)
        writer.writeheader()
        # Для каждого города и данных о погоде записываем строки
        for i, weather_data in enumerate(weather_data_list):
            for daily_forecast in weather_data['DailyForecasts']:
                date = daily_forecast['Date']
                min_temp = daily_forecast['Temperature']['Minimum']['Value']
                max_temp = daily_forecast['Temperature']['Maximum']['Value']
                average_temperature = (min_temp + max_temp) / 2
                wind_speed = daily_forecast['Day']['Wind']['Speed']['Value']
                precipitation_probability = daily_forecast['Day']['PrecipitationProbability']
                weather_condition = check_bad_weather(average_temperature, wind_speed, precipitation_probability)

                # Составляем строку данных для записи
                weather_data_row = {
                    'City': city_names[i],
                    'Date': date,
                    'Average Temperature': average_temperature,
                    'Wind Speed': wind_speed,
                    'Precipitation Probability': precipitation_probability,
                    'Condition': weather_condition
                }
                writer.writerow(weather_data_row)


def get_city_key(city_name):
    location_url = f"{BASE_URL}/locations/v1/cities/search"
    params = {'q': city_name, 'apikey': API_KEY, 'language': 'ru-ru'}
    response = requests.get(location_url, params=params)
    if response.status_code == 200:
        data = response.json()
        if data:
            return data[0]["Key"]
    return None


def get_weather_data(city, days):
    city_key = get_city_key(city)
    if city_key:
        url = f'{BASE_URL}/forecasts/v1/daily/{days}day/{city_key}'
        params = {'apikey': API_KEY, 'details': 'true'}
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
    return None


def check_bad_weather(temperature, wind_speed, precipitation_value):
    if temperature < 0 or temperature > 35:
        return "неблагоприятные"
    if wind_speed > 50:
        return "неблагоприятные"
    if precipitation_value > 70:
        return "неблагоприятные"
    return "благоприятные"


def process_weather_data(start_city, end_city, intermediate_cities, days):
    city_names = [start_city] + [city.strip() for city in intermediate_cities if city.strip()] + [end_city]
    print("Processing cities:", city_names)  # Для отладки: выводим города
    weather_data_list = []

    # Получаем данные о погоде для каждого города
    for city in city_names:
        city_weather_data = get_weather_data(city.strip(), days)
        if city_weather_data:
            weather_data_list.append(city_weather_data)

    # Сохраняем данные о погоде в CSV файл
    save_weather_data_to_csv(weather_data_list, 'weather_forecast.csv', city_names)
    return weather_data_list, city_names

# Главная страница маршрута
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        start_city = request.form['start_city']
        end_city = request.form['end_city']

        # Обрабатываем промежуточные города
        intermediate_cities = request.form.get('intermediate_city', '').split(',')
        intermediate_cities = [city.strip() for city in intermediate_cities if city.strip()]  # Убираем лишние пробелы

        print("Start city:", start_city)
        print("End city:", end_city)
        print("Intermediate cities:", intermediate_cities)

        city_names = [start_city] + intermediate_cities + [end_city]
        print("Processed city names:", city_names)

        # Получаем данные о погоде
        days = int(request.form['days'])
        weather_data_list, city_names = process_weather_data(start_city, end_city, intermediate_cities, days)

        if weather_data_list:
            return redirect(url_for('dashboard'))
        else:
            return render_template('error.html', message="Ошибка получения данных о погоде.")

    return render_template('index.html')

# Страница с графиками
@app.route('/dashboard')
def dashboard():
    df = pd.read_csv('weather_forecast.csv')

    cities = df['City'].unique()

    temperature_data = []
    wind_speed_data = []
    condition_data = []

    for city in cities:
        city_data = df[df['City'] == city]

        # График средней температуры
        temperature_data.append(go.Scatter(
            x=city_data['Date'],
            y=city_data['Average Temperature'],
            mode='lines+markers',
            name=f'Average Temperature ({city})',
            line=dict(width=2)
        ))

        # График скорости ветра
        wind_speed_data.append(go.Scatter(
            x=city_data['Date'],
            y=city_data['Wind Speed'],
            mode='lines+markers',
            name=f'Wind Speed ({city})',
            line=dict(width=2)
        ))

        # График погодных условий
        condition_data.append(go.Scatter(
            x=city_data['Date'],
            y=city_data['Condition'],
            mode='markers',
            name=f'Condition ({city})',
            marker=dict(
                color=city_data['Condition'].map({
                    "благоприятные": "green",
                    "неблагоприятные": "red"
                }),
                size=10,
                symbol='circle'
            )
        ))

    # Отображаем графики на странице
    dash_app.layout = html.Div(children=[
        html.H1(children='Weather Forecast'),

        dcc.Graph(
            id='temperature-graph',
            figure={
                'data': temperature_data,
                'layout': go.Layout(
                    title='Average Temperature',
                    xaxis={'title': 'Date'},
                    yaxis={'title': 'Temperature (°C)'},
                    hovermode='closest'
                )
            }
        ),

        dcc.Graph(
            id='wind-speed-graph',
            figure={
                'data': wind_speed_data,
                'layout': go.Layout(
                    title='Wind Speed',
                    xaxis={'title': 'Date'},
                    yaxis={'title': 'Wind Speed (km/h)'},
                    hovermode='closest'
                )
            }
        ),

        dcc.Graph(
            id='condition-graph',
            figure={
                'data': condition_data,
                'layout': go.Layout(
                    title='Weather Conditions',
                    xaxis={'title': 'Date'},
                    yaxis={'title': 'Condition'},
                    hovermode='closest'
                )
            }
        )
    ])

    return dash_app.index()

# Запуск приложения
if __name__ == '__main__':
    app.run()
