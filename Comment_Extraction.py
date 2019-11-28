#Comment extraction from YouTube channels 
#Step 1: Connection with the database
#Step 2: Comment extraction using the https://github.com/egbertbouman/youtube-comment-downloader
#Step 3: Insert into database


import pandas as pd
import os.path
import os
import sys
import time
import json
import requests
import argparse
import lxml.html
import io
import logging
import pyodbc 

from lxml.cssselect import CSSSelector

YOUTUBE_COMMENTS_URL = 'https://www.youtube.com/all_comments?v={youtube_id}'
YOUTUBE_COMMENTS_AJAX_URL = 'https://www.youtube.com/comment_ajax'

USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.2564.116 Safari/537.36'

logging.basicConfig(filename='./applog.log', filemode='w', format='%(name)s - %(levelname)s - %(message)s')

def find_value(html, key, num_chars=2):
    pos_begin = html.find(key) + len(key) + num_chars
    pos_end = html.find('"', pos_begin)
    return html[pos_begin: pos_end]


def extract_comments(html):
    tree = lxml.html.fromstring(html)
    item_sel = CSSSelector('.comment-item')
    text_sel = CSSSelector('.comment-text-content')
    time_sel = CSSSelector('.time')
    author_sel = CSSSelector('.user-name')

    for item in item_sel(tree):
        yield {'cid': item.get('data-cid'),
               'text': text_sel(item)[0].text_content(),
               'time': time_sel(item)[0].text_content().strip(),
               'author': author_sel(item)[0].text_content()}


def extract_reply_cids(html):
    tree = lxml.html.fromstring(html)
    sel = CSSSelector('.comment-replies-header > .load-comments')
    return [i.get('data-cid') for i in sel(tree)]


def ajax_request(session, url, params, data, retries=1, sleep=20):
    for _ in range(retries):
        response = session.post(url, params=params, data=data)
        if response.status_code == 200:
            response_dict = json.loads(response.text)
            return response_dict.get('page_token', None), response_dict['html_content']
        else:
            logging.warning(params["filter"])

            #time.sleep(sleep)


def download_comments(youtube_id, sleep=1):
    session = requests.Session()
    session.headers['User-Agent'] = USER_AGENT

    # Get Youtube page with initial comments
    response = session.get(YOUTUBE_COMMENTS_URL.format(youtube_id=youtube_id))
    html = response.text
    reply_cids = extract_reply_cids(html)

    ret_cids = []
         
        
        
    for comment in extract_comments(html):
        ret_cids.append(comment['cid'])
        yield comment

    page_token = find_value(html, 'data-token')
    session_token = find_value(html, 'XSRF_TOKEN', 4)

    first_iteration = True

    # Get remaining comments (the same as pressing the 'Show more' button)
    while page_token:
        data = {'video_id': youtube_id,
                'session_token': session_token}

        params = {'action_load_comments': 1,
                  'order_by_time': True,
                  'filter': youtube_id}

        if first_iteration:
            params['order_menu'] = True
        else:
            data['page_token'] = page_token

        response = ajax_request(session, YOUTUBE_COMMENTS_AJAX_URL, params, data)
        if not response:
            break

        page_token, html = response

        reply_cids += extract_reply_cids(html)
        for comment in extract_comments(html):
            if comment['cid'] not in ret_cids:
                ret_cids.append(comment['cid'])
                yield comment

        first_iteration = False
        time.sleep(sleep)

    # Get replies (the same as pressing the 'View all X replies' link)
    for cid in reply_cids:
        data = {'comment_id': cid,
                'video_id': youtube_id,
                'can_reply': 1,
                'session_token': session_token}

        params = {'action_load_replies': 1,
                  'order_by_time': True,
                  'filter': youtube_id,
                  'tab': 'inbox'}

        response = ajax_request(session, YOUTUBE_COMMENTS_AJAX_URL, params, data)
        if not response:
            break

        _, html = response

        for comment in extract_comments(html):
            if comment['cid'] not in ret_cids:
                ret_cids.append(comment['cid'])
                yield comment
        time.sleep(sleep)


def downloadingcontent(youtube_id, output,youtube_title,youtube_link,youtube_views,youtube_date,channel_name):

    try:
        if not youtube_id or not output:
            raise ValueError('you need to specify a Youtube ID and an output filename')
       
        print('Downloading Youtube comments for video:', youtube_id)
        count = 0
        
        save_path = './Data'
        completeName = os.path.join(save_path, output+".json")  

        
        
        with io.open(completeName, 'w', encoding='utf8') as fp:

            for comment in download_comments(youtube_id):

                comment.update({"Title":youtube_title,"Link":youtube_link,"youtube_views":youtube_views,"Date":youtube_date })

                try:
                    cursor = cnxn.cursor()
                    #Change to include channel id TODOMCH
                    cursor.execute("insert into dbo.VideoComment([CommentID], [CommentText] ,[CommentTime] ,[CommentAuthor] ,[VideoTitle] ,[VideoLink] ,[VideoViews] ,[VideoPublishedDate],[Channel]) values(?, ?, ?, ?, ?, ?, ?, ?,?);", (comment["cid"], comment["text"], comment["time"], comment["author"], comment["Title"], comment["Link"], comment["youtube_views"], comment["Date"],channel_name))
                    cnxn.commit()
                except Exception as ex:
                    logging.warning(ex)             

                print(json.dumps(comment, ensure_ascii=False), file=fp)
                count += 1
                sys.stdout.write('Downloaded %d comment(s)\r' % count)
                sys.stdout.flush()

        fp.close()
        print('\nDone!')


    except Exception as e:
        print('Error:', str(e))
        sys.exit(1)





#Lists of videos for each channel

data_l = pd.read_csv("./imetaxas2016YouTube.csv") 
#data_l = pd.read_csv("./imetaxas2015YouTube.csv") 
#data_l = pd.read_csv("./xagrnetYouTube.csv") 
#data_l = pd.read_csv("./xryshayghcomYouTube.csv.csv") 

data_l=data_l.iloc[:,0:4]
data_l=data_l.rename(index=str, columns={"Field1_Text": "Title", "Field1_Link": "Link","Field2": "Views","Field3": "Date_published"})
data_temp=data_l.copy()
data_temp.Link=data_temp.Link.str.strip('https://www.youtube.com/watch?v=')


cnxn = pyodbc.connect("Driver={SQL Server Native Client 11.0};"
                      "Server=kimsufi.pro-solution.dk;"
                      "Database=mch;"
                      "uid=mch;pwd=Maria123!;")


#Channel names

channel_name="imetaxas2016"
# channel_name="imetaxas2015"
# channel_name="xagrnet"
# channel_name="xryshayghcom"

for i in range (0,len(data_temp.Link)):
    downloadingcontent(data_temp.Link[i],data_temp.Link[i],data_temp.Title[i],data_l.Link[i],data_temp.Views[i],data_temp.Date_published[i],channel_name)