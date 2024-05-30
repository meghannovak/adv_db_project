from flask import Flask, render_template, request, session, redirect, url_for, jsonify
import sys
import os
import cx_Oracle
from jinja2 import Environment
from classes import User
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

g_user = None

def init_session(connection, requestedTag_ignored):
    cursor = connection.cursor()
    cursor.execute("""
        ALTER SESSION SET
            TIME_ZONE = 'UTC'
            NLS_DATE_FORMAT = 'YYYY-MM-DD HH24:MI'""")

def start_pool():

    # pool min/max is how how many connections can be used at a time
    pool_min = 4
    pool_max = 4
    pool_inc = 0
    pool_gmd = cx_Oracle.SPOOL_ATTRVAL_WAIT

    print('Connecting to', os.environ.get("PYTHON_CONNECTSTRING"))

    pool = cx_Oracle.SessionPool(user=os.environ.get("PYTHON_USERNAME"),
                                password=os.environ.get("PYTHON_PASSWORD"),
                                dsn=os.environ.get("PYTHON_CONNECTSTRING"),
                                min=pool_min,
                                max=pool_max,
                                increment=pool_inc,
                                threaded=True,
                                getmode=pool_gmd,
                                sessionCallback=init_session)
    
    return pool

def get_url_title(url):
    try:
        # Fetch the HTML content of the webpage
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        # Parse the HTML content
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find the title tag
        title_tag = soup.find('title')

        if title_tag:
            # Return the text inside the title tag
            return title_tag.get_text()
        else:
            return "Title not found"

    except requests.exceptions.RequestException as e:
        # Handle any errors that occur during the request
        print("Error fetching URL:", e)
        return None

@app.route('/')
def home():

    global g_user

    connection = pool.acquire()
    cursor = connection.cursor()
    cursor.execute("select * from ads where yr is not null order by yr desc")
    ads = cursor.fetchall()

    ad_previews = []
    for ad in ads:
        if ad[5]:
            embed_url = f'https://www.youtube.com/embed/{ad[5][ad[5].find("?v=")+3:]}'
            img_url = f'http://img.youtube.com/vi/{ad[5][ad[5].find("?v=")+3:]}/0.jpg'
            new_tuple = tuple(
                embed_url if i == 5 else (img_url if i == 4 else value)
                for i, value in enumerate(ad)
            )
            ad_previews.append(new_tuple)
   
    cursor.execute("select title from ads")
    titles = [title[0] for title in cursor.fetchall()]

    return render_template('index.html', ads=ad_previews, titles=titles, user=g_user)

@app.route('/analytics')
def analytics():
    return render_template('analytics.html', user=g_user)

@app.route('/buzz/<ad_id>', methods=['GET', 'POST'])
def buzz(ad_id):
#    if request.method == 'POST':
        ad_id = int(ad_id)
        connection = pool.acquire()
        cursor = connection.cursor()
        cursor.execute("select * from ads where ad_id = :1", [ad_id])
        ads = cursor.fetchall()
        ad = ads[0]
        if ad[5]:
            embed_url = f'https://www.youtube.com/embed/{ad[5][ad[5].find("?v=")+3:]}'
    
        tags = []
        if ad[6] =='True':
            tags.append("is_funny")
        if ad[7] =='True':
            tags.append("shows_product")
        if ad[8] =='True':
            tags.append("is_patriotic")
        if ad[9] =='True':
            tags.append("shows_celebrity")
        if ad[10] =='True':
            tags.append("has_danger")
        if ad[11] =='True':
            tags.append("has_animal")
        if ad[12] =='True':
            tags.append("uses_sex")
    
        caption_path = f'data/captions/{ad_id}.txt'
        if os.path.exists(caption_path):
            with open(caption_path) as f:
                cap = f.read()
                if len(cap) == 0:
                    cap=None

        else: cap=None

        desc_path = f'data/descrs/{ad_id}.txt'
        if os.path.exists(desc_path):
            with open(desc_path) as f:
                desc = f.read()
        else: desc=None
        if cap is not None:
            cursor.execute("select * from emotions where ad_id= :1", [ad_id])
            response = cursor.fetchall()
            emotions = []
            if len(response) > 0:
                for item in response[0][1:]:
                    emotions.append(float(item))
                emotions = [round(x*100, 2) for x in emotions]
            else: emotions=None
        else: emotions=None

        # Get comments for video
        comm_path = f'data/comments/{ad_id}.txt'
        if os.path.exists(comm_path):
            with open(comm_path) as f:
                comments = f.readlines()
        else:
            comments = []
        cursor.execute("select * from comments where ad_id= :1", [ad_id])
        response = cursor.fetchall()
        comm_analyz = []
        if len(response) > 0:
            for item in response[0][1:]:
                comm_analyz.append(float(item))
            comm_analyz = [round(x*100, 2) for x in comm_analyz]
        else: comm_analyz=None

        # See if ad is a favorite
        is_favorite = False
        if g_user: 
            cursor.execute("select * from favorites where ad_id= :1 and username= :2", [ad_id, g_user.username])
            favorite = cursor.fetchall()
            if len(favorite) != 0:
                is_favorite = True

        # Get related articles
        cursor.execute("select article_url from articles where ad_id = :1", [ad_id])
        articles = cursor.fetchall()
        article_titles = []

        for article in articles:
            article = article[0][1:-1]
            title = get_url_title(article)

            if title == None:
                title = article.replace('https://', '')
                title = title.replace('http://', '')
                title = title.replace('www.', '')
                
                ind = title.find('.com')
                if ind != -1:
                    title = title[:ind]
            article_titles.append(title)

        articles = zip(articles, article_titles)

        return render_template('buzz.html', ad=ad, url=embed_url, caption=cap,desc=desc, emotions=emotions, tags=tags, user=g_user, comments=comments, comm_analyz=comm_analyz, is_favorite=is_favorite, articles=articles)
    
 #   return redirect('/archive')

@app.route('/favorites', methods=['GET', 'POST'])
def favorites():
    global g_user
    
    if g_user is None:
        return redirect(url_for('home'))

    # Get all brand names
    connection = pool.acquire()
    cursor = connection.cursor()
    cursor.execute('select distinct brand from ads')
    fetched = cursor.fetchall()
    cursor.close()

    all_brands = [ b[0] for b in fetched if b[0] is not None ]
    all_brands = sorted(all_brands, key=lambda b: b)

    connection = pool.acquire()
    cursor = connection.cursor()
    cursor.execute('select * from ads, favorites where username= :1 and ads.ad_id = favorites.ad_id', [g_user.username])
    ads = cursor.fetchall()
    ad_previews = []

    if request.method == 'GET':
        for ad in ads:
            if ad[5]:
                embed_url = f'http://img.youtube.com/vi/{ad[5][ad[5].find("?v=")+3:]}/0.jpg'
                new_tuple = tuple(embed_url if i == 5 else value for i, value in enumerate(ad))
                ad_previews.append(new_tuple) 
                #return render_template('favorites.html', ads=ad_previews, all_brands=all_brands, user=g_user)
    
    if request.method == 'POST':
        # Get video quality filters
        qualities = []

        if 'is_funny' in request.form:
            qualities.append('is_funny')
        if 'shows_product_quickly' in request.form:
            qualities.append('shows_product_quickly')
        if 'is_patriotic' in request.form:
            qualities.append('is_patriotic')
        if 'shows_celebrity' in request.form:
            qualities.append('shows_celebrity')
        if 'has_danger' in request.form:
            qualities.append('has_danger')
        if 'has_animal' in request.form:
            qualities.append('has_animal')
        if 'uses_sex' in request.form:
            qualities.append('uses_sex')

        # Get brand filters
        brands = []
        for b in all_brands:
            if b in request.form:
                brands.append(b)

        # Add all selected filter options to query
        query = f"select * from ads, favorites where username='{g_user.username}' and ads.ad_id = favorites.ad_id"
        if qualities != []:
            query += ' and '

            for i, q in enumerate(qualities):
                query += f'{q} = \'True\' '

                if i != len(qualities) - 1:
                    query += 'and '

            print(query)

        if brands != []:
            if qualities == []:
                query += ' where '
            else:
                query += ' and '

            for i, b in enumerate(brands):
                query += f'brand = \'{b}\''

                if i != len(brands) - 1:
                    query += ' or '

        # Fetch ads that match filters
        connection = pool.acquire()
        cursor = connection.cursor()
        print(query)
        cursor.execute(query)
        ads = cursor.fetchall()
        cursor.close()

        # Sort ads accordingly
        if 'sort-options' in request.form:
            sort = request.form['sort-options']

            if sort == 'sort-atoz':
                ads = sorted(ads, key=lambda ad: ad[2])
            elif sort == 'sort-ztoa':
                ads = sorted(ads, key=lambda ad: ad[2], reverse=True)
            elif sort == 'sort-yeardesc':
                ads = sorted(ads, key=lambda ad: ad[1] if ad[1] is not None else -1, reverse=True)
            elif sort == 'sort-yearasc':
                ads = sorted(ads, key=lambda ad: ad[1] if ad[1] is not None else 9999)
        else:
            sort = None

        ad_previews = []
        for ad in ads:
            if ad[5]:
                embed_url = f'http://img.youtube.com/vi/{ad[5][ad[5].find("?v=")+3:]}/0.jpg'
                new_tuple = tuple(embed_url if i == 5 else value for i, value in enumerate(ad))
                ad_previews.append(new_tuple)

        filters = brands + qualities
        
        return render_template('favorites.html', ads=ad_previews, sort=sort, filters=filters, all_brands=all_brands, user=g_user)
    return render_template('favorites.html', ads=ad_previews, all_brands=all_brands, user=g_user)

@app.route('/add/<ad_id>', methods=['GET', 'POST'])
def add(ad_id):
    global g_user

    if g_user:
        connection = pool.acquire()
        cursor = connection.cursor()

        # Checks if ad is already in favorites
        cursor.execute("select * from favorites where ad_id= :1 and username= :2", [ad_id, g_user.username])
        favorite = cursor.fetchall()

        if len(favorite) == 0:
            cursor.execute('insert into favorites (username, ad_id) values (:1, :2)', [g_user.username, ad_id])
            connection.commit()
            return redirect(url_for('buzz', ad_id=ad_id))

        else: 
            cursor.execute('delete from favorites where username= :1 and ad_id= :2', [g_user.username, ad_id])
            connection.commit()
            return redirect(url_for('buzz', ad_id=ad_id))

    else:
        return redirect(url_for('login'))

@app.route('/archive', methods=['GET', 'POST'])
def archive():

    # Get all brand names
    connection = pool.acquire()
    cursor = connection.cursor()
    cursor.execute('select distinct brand from ads')
    fetched = cursor.fetchall()
    cursor.close()
    all_brands = [ b[0] for b in fetched if b[0] is not None ]
    all_brands = sorted(all_brands, key=lambda b: b)

    if request.method == 'POST':
        # Get video quality filters
        qualities = []

        if 'is_funny' in request.form:
            qualities.append('is_funny')
        if 'shows_product_quickly' in request.form:
            qualities.append('shows_product_quickly')
        if 'is_patriotic' in request.form:
            qualities.append('is_patriotic')
        if 'shows_celebrity' in request.form:
            qualities.append('shows_celebrity')
        if 'has_danger' in request.form:
            qualities.append('has_danger')
        if 'has_animal' in request.form:
            qualities.append('has_animal')
        if 'uses_sex' in request.form:
            qualities.append('uses_sex')

        # Get brand filters
        brands = []
        for b in all_brands:
            if b in request.form:
                brands.append(b)

        # Get year filter
        year = -1
        try:
            if 'year' in request.form and int(request.form['year']) <= 2024 and int(request.form['year']) >= 1980:
                year = request.form['year']
        except:
            pass

        # Add all selected filter options to query
        query = 'select * from ads'
        if qualities != []:
            query += ' where '

            for i, q in enumerate(qualities):
                query += f'{q} = \'True\' '

                if i != len(qualities) - 1:
                    query += 'and '

        if brands != []:
            if qualities == []:
                query += ' where '
            else:
                query += ' and '

            for i, b in enumerate(brands):
                query += f'brand = \'{b}\''

                if i != len(brands) - 1:
                    query += ' or '
        
        if year != -1:
            if brands == [] and qualities == []:
                query += f' where yr={year}'
            else:
                query += f' and yr={year}'

        print(query)
        # Fetch ads that match filters
        connection = pool.acquire()
        cursor = connection.cursor()
        cursor.execute(query)
        ads = cursor.fetchall()
        cursor.close()

        # Sort ads accordingly
        if 'sort-options' in request.form:
            sort = request.form['sort-options']
        
            if sort == 'sort-atoz':
                ads = sorted(ads, key=lambda ad: ad[2])
            elif sort == 'sort-ztoa':
                ads = sorted(ads, key=lambda ad: ad[2], reverse=True)
            elif sort == 'sort-yeardesc':
                ads = sorted(ads, key=lambda ad: ad[1] if ad[1] is not None else -1, reverse=True)
            elif sort == 'sort-yearasc':
                ads = sorted(ads, key=lambda ad: ad[1] if ad[1] is not None else 9999)
        else:
            sort = None

        if query is "select * from ads":
            ads = sorted(ads, key=lambda ad: ad[1] if ad[1] is not None else -1, reverse=True)
            
        ad_previews = []
        for ad in ads:
            if ad[5]:
                embed_url = f'http://img.youtube.com/vi/{ad[5][ad[5].find("?v=")+3:]}/0.jpg'
                new_tuple = tuple(embed_url if i == 5 else value for i, value in enumerate(ad))
                ad_previews.append(new_tuple)

        filters = brands + qualities

        return render_template('archive.html', ads=ad_previews, sort=sort, filters=filters, year=year, all_brands=all_brands, user=g_user)

    if request.method == 'GET':
        connection = pool.acquire()
        cursor = connection.cursor()
        cursor.execute("select * from ads")
        ads = cursor.fetchall()
        cursor.close()

    ads = sorted(ads, key=lambda ad: ad[1] if ad[1] is not None else -1, reverse=True)
    ad_previews = []
    for ad in ads:
        if ad[5]:
            embed_url = f'http://img.youtube.com/vi/{ad[5][ad[5].find("?v=")+3:]}/0.jpg'
            new_tuple = tuple(embed_url if i == 5 else value for i, value in enumerate(ad))
            ad_previews.append(new_tuple)

    return render_template('archive.html', ads=ad_previews, all_brands=all_brands, user=g_user)

@app.route('/login', methods=["GET", "POST"])
def login():
    global g_user

    if request.method == 'POST':
        connection = pool.acquire()
        cursor = connection.cursor()
        username = request.form['username']
        password = request.form['password']
        cursor = connection.cursor()
        cursor.execute("select * from users where username = :1 and password = :2", [username, password])
        user = cursor.fetchall()
        if not user:
            print('user does not exist')
        else:
            g_user = User(user[0][0], user[0][3], user[0][1], user[0][2])
            return redirect(url_for('favorites'))

    return render_template('login.html')

@app.route('/createaccount', methods=["GET", "POST"])
def createaccount():
    global g_user

    if request.method == "POST":
        first_name = request.form["first_name"]
        last_name = request.form["last_name"]
        username = request.form["username"]
        password = request.form["password"]
        connection = pool.acquire()
        cursor = connection.cursor()
        cursor.execute("select * from users where username = :1", [username])
        existing_user = cursor.fetchall()

        if existing_user:
            cursor.close()
            return render_template('createaccount.html')
        else:
            cursor.execute("insert into users (first_name, last_name, username, password) values (:1, :2, :3, :4)", (first_name, last_name, username, password))
            connection.commit()
            cursor.close()
            g_user = User(username, password, first_name, last_name)
            print("G_USER create account:", g_user)
            return redirect(url_for('favorites'))

    return render_template('createaccount.html')

@app.route('/signout', methods=["GET", "POST"])
def logout():
    global g_user
    g_user = None

    return redirect(url_for('home'))


@app.route('/about', methods=["GET", "POST"])
def about():
    global g_user

    return render_template('about.html', user=g_user)

if __name__ == '__main__':

    pool = start_pool()
    app.run(host='0.0.0.0', port=8007)


