"Emily Mattlin, Sarah Pardo, Safiya Sirota, Mileva Van Tuyl"
from flask import (Flask, render_template, make_response, url_for, request,
                   redirect, flash, session, send_from_directory, jsonify)
from werkzeug.utils import secure_filename
import os
import cs304dbi as dbi
import functions

UPLOAD_FOLDER = 'upload_folder'
ALLOWED_EXTENSIONS = {'pdf'}
PORTRAIT_FOLDER = 'upload_folder'


app = Flask(__name__)

from flask_cas import CAS

CAS(app)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PORTRAIT_FOLDER'] = PORTRAIT_FOLDER

app.config['CAS_SERVER'] = 'https://login.wellesley.edu:443'

import random

app.secret_key = 'your secret here'
# replace that with a random key
app.secret_key = ''.join([ random.choice(('ABCDEFGHIJKLMNOPQRSTUVXYZ' +
                                          'abcdefghijklmnopqrstuvxyz' +
                                          '0123456789'))
                           for i in range(20) ])

# This gets us better error messages for certain common request errors
app.config['TRAP_BAD_REQUEST_ERRORS'] = True

app.config['CAS_LOGIN_ROUTE'] = '/module.php/casserver/cas.php/login'
app.config['CAS_LOGOUT_ROUTE'] = '/module.php/casserver/cas.php/logout'
app.config['CAS_VALIDATE_ROUTE'] = '/module.php/casserver/serviceValidate.php'
app.config['CAS_AFTER_LOGIN'] = 'logged_in'
# Doesn't redirect properly, but not a problem to fix--it is okay:
app.config['CAS_AFTER_LOGOUT'] = 'after_logout'

@app.route('/')
def index():
    '''Sends user to the syllabo home page'''
    return render_template('home.html', courses = functions.getRecommended())

@app.route('/create/', methods=['GET','POST'])
def createCourse():
    '''Sends user to the create course page. When they post the form, a new course is created'''
    if request.method == 'GET':
        if 'CAS_ATTRIBUTES' not in session:
            return redirect(url_for('login'))
        return render_template('create_course.html')
    else:
        conn = dbi.connect()
        values = request.form
        isNew = functions.isCourseNew(conn, values['course-title'], values['course-prof'], 
                values['course-sem'], values['course-year'])
        if isNew == True:
            cid = functions.insertCourse(conn, list(values.values()))
            flash('Your updates have been made!')
            return redirect(url_for('uploadSyllabus', n = cid))
        else:
            flash('This course already exists!')
            return redirect(url_for('createCourse'))

@app.route('/upload/<int:n>', methods=['GET','POST'])
def uploadSyllabus(n):
    '''After creating a course, a student may upload a syllabus pdf to that course page'''
    if request.method == 'GET':
        return render_template('syl_upload.html')
    else:
        if 'file' not in request.files:
            flash('No file part')
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
        if file and functions.allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        functions.saveToDB(n, file.filename)
        return render_template('home.html', courses = functions.getRecommended())

@app.route('/explore/', methods = ['GET'])
def explore(): 
    '''Sends user to the explore page, which shows every course in the db'''
    conn = dbi.connect()
    allCourses = functions.getAllCourses(conn)
    return render_template('explore.html', 
                courses = allCourses, query = None)
    
@app.route('/search/', methods = ['GET']) 
def search(): 
    '''Allows user to search for courses by title, course number, department, or professor'''
    conn = dbi.connect()
    search = request.args.get('search')
    kind = request.args.get('type') 

    # Check kind type is valid
    if (kind == "title" or kind == "dep" or kind == "cnum" or kind == "prof"):
        if (kind == "prof"):
            courseResultsByProf = functions.getCoursesByProf(conn, search)
        else: 
            courseResults = functions.getCourses(conn, search, kind)
        numSections = functions.numSections(conn, search, kind)

        # No results: redirect user to create a new course
        if numSections == 0:
            flash ('No results for {} in the database.'.format(search))
            return redirect(url_for('createCourse')) 

        # One result: redirect user to specific course page
        elif numSections == 1: 
            cid = functions.getOneResult(conn, search, kind)
            return redirect(url_for('showCourse', cid = cid))
                
        # Multiple results: display all the results
        else: 

            if (kind == "prof"):
                return render_template('prof_search_results.html', 
                profs=courseResultsByProf, query = search)
            else: 
                return render_template('search_results.html', 
                courses = courseResults, query = search)
        
    # Invalid kind type
    else: 
        flash ('Invalid value entered for type field.')
        return redirect(url_for('createCourse')) 

@app.route('/course/<cid>', methods=['GET','POST'])
def showCourse(cid):
    '''directs the user an individual course page for unique semester, year, and prof'''
    conn = dbi.connect()
    basics = functions.getBasics(cid)
    if request.method == 'GET':
        avgRatings = functions.getAvgRatings(conn, cid)
        comments = functions.getComments(conn, cid) 
        return render_template('course_page.html', basics = basics, avgRatings = avgRatings, 
                                comments=comments)
    elif request.method == 'POST':
        action = request.form.get("submit")
        if action == 'Add to Favorites' :
            try: 
                bNum = functions.getBNum()
                print(bNum)
                functions.addFavorite(conn, bNum, basics['cid'])
                avgRatings = functions.getAvgRatings(conn, cid)
                comments = functions.getComments(conn, cid)
                flash('Course added to favorites')
                return render_template('course_page.html', basics = basics, avgRatings = avgRatings, 
                                comments=comments)
            except Exception as err:
                avgRatings = functions.getAvgRatings(conn, cid)
                comments = functions.getComments(conn, cid)
                flash('Please log in to favorite a course!') 
                return render_template('course_page.html', basics = basics, avgRatings = avgRatings, 
                                comments=comments)
        elif action == 'Rate':
            print('trying to rate/comment')
            #user is rating (which includes commenting) the course.
            uR = request.form.get('usefulRate')
            dR = request.form.get('diffRate')
            rR = request.form.get('relevRate')
            eR = request.form.get('expectRate')
            hW = request.form.get('hoursWk')
            comment = request.form.get('new_comment')
            functions.makeRatings(functions.getBNum(), cid, rR, uR, dR, eR, hW, comment) 
            #have to recalculate the ratings and fetch the comments again
            avgRatings = functions.getAvgRatings(conn, cid)
            comments = functions.getComments(conn, cid)
            #now we render the page again
            return render_template('course_page.html', basics = basics, avgRatings = avgRatings, 
                                    comments=comments)

@app.route('/pdf/<cid>')
def getPDF(cid):
    '''Displays the course syllabus PDF on the course page'''
    conn = dbi.connect()
    curs = dbi.dict_cursor(conn)
    curs.execute(
        '''select filename from syllabi where cid = %s''',
        [cid])
    row = curs.fetchone()
    print(row)
    if row != None and row['filename'] != '':
        return send_from_directory(app.config['UPLOAD_FOLDER'],row['filename'])
    return send_from_directory(app.config['UPLOAD_FOLDER'],'NoSyllabus.pdf')
   
@app.route('/pic/<bNum>')
def getPic(bNum):
    '''displays the profile picture of a student on their profile page'''
    conn = dbi.connect()
    curs = dbi.dict_cursor(conn)
    curs.execute(
        '''select filename from portrait where bNum = %s''',
        [bNum])
    row = curs.fetchone()
    if row != None:
        return send_from_directory(app.config['UPLOAD_FOLDER'],row['filename'])
    return send_from_directory(app.config['UPLOAD_FOLDER'],'NoPropic.png')
    

@app.route('/course/<cid>/update', methods=['GET','POST'])
def update(cid):
    '''prompts user to fill out an update form for outdated or missing course info'''
    basics = functions.getBasics(cid)
    if request.method == 'GET':
        if 'CAS_ATTRIBUTES' not in session:
            return redirect(url_for('login'))
        return render_template('update_course.html', basics = basics)
    elif request.method == 'POST':
        updateValues = request.form.to_dict()
        #updateCourse is a nonfruitful function, takes in the form data and the cid
        functions.updateCourse(updateValues, cid)
        flash('Successfully updated course!')
        return redirect(url_for('updateSyllabus', cid = cid))

'''Just a separate route from the original upload syllabus because the HTML and messaging is slightly diff'''
@app.route('/updatesyllabus/<int:cid>', methods=['GET','POST'])
def updateSyllabus(cid):
    '''allows user to upload a new syllabus'''
    #uses same functions as upload syllabus...not updating the course table
    if request.method == 'GET':
        return render_template('update_syl.html')
    else:
        if 'file' not in request.files:
            flash('No file part')
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
        if file and functions.allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        functions.saveToDB(cid, file.filename)
        #bring them back to the updated course page
        return redirect(url_for('showCourse', cid = cid))

'''Functions below have to do with logging in, creating a profile, seeing your profile,
and logging out.'''

@app.route('/loginPage/', methods=['GET'])
def login():
    '''sends user to login using Wellesley Authentification'''
    if '_CAS_TOKEN' in session:
        token = session['_CAS_TOKEN']
    if 'CAS_USERNAME' in session:
        is_logged_in = True
        username = session['CAS_USERNAME']
    else:
        is_logged_in = False
        username = None
    if is_logged_in: # only occurs for first time login
        conn = dbi.connect()
        bNum = functions.getBNum()
        student = functions.getStudent(bNum)
        name = student[1]
        return redirect( url_for('profile', name = name) )
    else: 
        return render_template('login.html',
                           username=username,
                           is_logged_in=is_logged_in,
                           cas_attributes = session.get('CAS_ATTRIBUTES'))

# Log in CAS stuff:
@app.route('/logged_in/')
def logged_in():
    '''logs student in or sends them to create a profile if they don't have an account'''
    conn = dbi.connect()
    bNum = functions.getBNum()
    alreadyAMember = functions.checkUser(conn, bNum)
    # if profile already made, redirect to profile
    if(alreadyAMember):
        student = functions.getStudent(bNum)
        name = student[1]
        return redirect( url_for('profile', name = name) )
    else: # if not, create profile
        return redirect( url_for('createProfile') )

@app.route('/createProfile/', methods=['GET','POST'])
def createProfile():
    '''prompts user to fill out a form to create a profile'''
    if request.method == 'GET':
        return render_template('create_profile.html')
    else:
        values = request.form
        bNum = functions.getBNum()
        student_attributes = list(values.values())
        student_attributes.insert(0,bNum)
        studentInfo = functions.insertStudent(student_attributes)
        return redirect(url_for('uploadPic', n = bNum))

@app.route('/uploadPic/', methods=["GET", "POST"])
def uploadPic():
    '''prompts user to upload a profile picture for their account'''
    if request.method == 'GET':
        return render_template('portrait_upload.html')
    else:
        if 'file' not in request.files:
            flash('No file part')
        file = request.files['file']
        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            flash('No selected file')
        if file and functions.allowed_picture_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['PORTRAIT_FOLDER'], filename))
        bNum = functions.getBNum()
        student = functions.getStudent(bNum)
        name = student[1]
        functions.insertPicture(bNum, file.filename)
        return redirect(url_for('profile', name = name))

@app.route('/profile/<name>', methods =['GET', 'POST'])
def profile(name):
    '''displays the profile of a user. If it is their profile page they may update their picture or major'''
    student = functions.getStudentFromName(name)
    studentDict = {'bNum': student[0], 'name': student[1], 'email': student[3]}
    bNum = studentDict['bNum']
    if request.method == 'GET':
        studentDict['major'] = student[2]
        favorites = functions.getFavorites(bNum)
        comments = functions.getStudentComments(bNum)
        try:
            return render_template('profile_page.html', 
                    student = studentDict, favorites = favorites, comments = comments, cas_attributes = session.get('CAS_ATTRIBUTES'))
        except Exception as err:
            print(err)
            flash("Please log in to view profiles!")
            return redirect(url_for('login'))
    elif request.method == 'POST':
        newMajor = request.form.get('major')
        functions.updateMajor(newMajor, bNum)
        student = functions.getStudentFromName(name)
        studentDict['major'] = student[2]
        favorites = functions.getFavorites(bNum)
        comments = functions.getStudentComments(bNum)
        print(student)
        return render_template('profile_page.html', 
                student = studentDict, favorites = favorites, comments = comments, cas_attributes = session.get('CAS_ATTRIBUTES'))


@app.route('/after_logout/')
def after_logout():
    '''logs out the user'''
    flash('successfully logged out!')
    return redirect( url_for('login') )

application = app

if __name__ == '__main__':
    import sys, os
    if len(sys.argv) > 1:
        port=int(sys.argv[1])
        if not(1943 <= port <= 1950):
            print('For CAS, choose a port from 1943 to 1950')
            sys.exit()
    else:
        port=os.getuid()
    # the following database code works for both PyMySQL and SQLite3
    dbi.cache_cnf()
    dbi.use('syllabo_db')
    conn = dbi.connect()
    curs = dbi.dict_cursor(conn)
    # the following query works for both MySQL and SQLite
    curs.execute('select current_timestamp as ct')
    row = curs.fetchone()
    ct = row['ct']
    print('connected to Syllabo DB at {}'.format(ct))
    app.debug = True
    app.run('0.0.0.0',port)
