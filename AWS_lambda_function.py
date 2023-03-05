import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import re
import time
import datetime
import os
import glob
import boto3
from io import BytesIO, StringIO

# This version is adapted for AWS so that a scheduler could email me new events.
def lambda_handler(event, context):
    def get_html():
        with requests.Session() as session: # create a session so login is cached and cookies are stored

            # Get the authenticity token from the login page
            login_url = 'https://nhs.ticketsforgood.co.uk/users/sign_in'
            response = session.get(login_url)
            soup = BeautifulSoup(response.text, 'html.parser')
            authenticity_token = soup.find('input', {'name': 'authenticity_token'})['value']

            # Set up the login data and headers
            # username = USERNAME
            # password = PASSWORD


            login_data = {
                'authenticity_token': authenticity_token, # can't log in without token
                'user[email]': username,
                'user[password]': password,
                'commit': 'Log in' # this posts the log in
            }
            headers = {
                'Referer': login_url,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
            }

            # Login to the webpage
            session.post(login_url, data=login_data, headers=headers)

            # Access the webpage after logging in
            page_url = 'https://nhs.ticketsforgood.co.uk'
            response = session.get(page_url)
            soup = BeautifulSoup(response.content, 'html.parser')

            # find number of pages to search
            last_page_num_el = soup.find_all('li', class_='page-item')[-1].a['href']
            last_page_num = int(re.search('\d+', last_page_num_el).group())


            events_html_lst = []
            for i in range(last_page_num):
                url = rf'https://nhs.ticketsforgood.co.uk/?page={i+1}'
                response = session.get(url)
                soup = BeautifulSoup(response.content, 'html.parser')
                events = soup.find_all('div', class_="col-xl-3 col-lg-4 col-md-6 col-12") # all event html stored in this type of element
                events_html_lst += events
                time.sleep(0.2) # to avoid overloading server

            return events_html_lst

    def create_df(html_list):            
        events_list = []
        for event in html_lst:
            name = event.find('h5', class_="card-title fw-bold mb-3").string.strip('\n')
            info = [element.string.strip('\n') for element in event.find_all('div', class_='col')]
            location, dates, event_type = info
            try:
                try:
                    url_ext = event.find('a', class_="btn py-3 rounded-3 fw-bold stretched-link btn-primary")['href']
                except:
                    url_ext = event.find('a', class_="btn py-3 rounded-3 fw-bold stretched-link btn-secondary")['href']
            except:
                url_ext = event.find('a', class_="btn py-3 rounded-3 fw-bold stretched-link btn-light text-muted bg-disabled")['href']

            event_dic = {'name': name, 'event_type': event_type, 'location': location, 'dates': dates, 'url': url_ext}
            events_list.append(event_dic)

        df = pd.DataFrame(events_list)
        df.dates = df.dates.str.replace('\n', '')
        url_base = r"https://nhs.ticketsforgood.co.uk/"
        df['url'] = url_base + df.url

        return df


    def get_last_search(): 
        # df = pd.read_csv(r"s3://ticketsforgood/last-search.csv",
        #       storage_options={'key': key,
        #                        'secret': secret})
        
        bucket_name = 'ticketsforgood'
        file_name = 'last-search.csv'

        response = s3.get_object(Bucket=bucket_name, Key=file_name)
        content = response['Body'].read()
        df = pd.read_csv(BytesIO(content))
        return df


    def compare_previous_search(df):
        df_prev = get_last_search()
        # Create sets of url lists from both dataframes. return list of urls that are in newer df and not the other.
        names1 = set(df_prev.url)
        names2 = set(df.url)
        diff_list = [*names2.difference(names1)]
        changes = df.loc[df.url.isin(diff_list)]

        return changes




    # relevant AWS parameters
    key = SECRET
    secret = KEY
    key_deets = {'aws_access_key_id': key,
                'aws_secret_access_key': secret,
                'region_name': 'eu-west-2'}

    arn = ARN

    s3 = boto3.client('s3', **key_deets) # to access files
    ses = boto3.client('ses', **key_deets) # to email data



    html_lst = get_html()
    df = create_df(html_lst)
    comp = compare_previous_search(df)

    html = comp.to_html(index=False, )

    timestamp = datetime.datetime.now().strftime("%d/%m/%y-%H:%M")

    CHARSET = "UTF-8"
    # response = ses.send_email(
    #         Destination={"ToAddresses": ['callumtaylor955@gmail.com']},
    #         Message={
    #             "Body": {
    #                 "Html": {"Charset": CHARSET, "Data": html},
    #             },
    #             "Subject": {"Charset": CHARSET, "Data": 'Tickets for Good: New Events'},
    #         },
    #         Source='callumtaylor955@gmail.com',
    #     )

    
    
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_content = csv_buffer.getvalue()
    bucket_name = 'ticketsforgood'
    file_name = 'last-search.csv'

    s3.put_object(Bucket=bucket_name, Key=file_name, Body=csv_content)

    # df.to_csv("s3://ticketsforgood/last-search.csv",
    #           storage_options={'key': key,
    #                            'secret': secret},
    #          index=False) 
    
    
lambda_handler(1, 2)
