#!/usr/bin/env python

##############################################################################
#
# Copyright (c) 2009-2010 log1 (mailto: log1@poczta.fm). All Rights Reserved.
# 
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License,
# or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
##############################################################################

__version__ = "Version: 3v1"
__author__ = ("log1@poczta.fm (Kuba Kuropatnicki)")
__license__ = 'GPL v3'

# monkey patch :)
import pickle
import marshal
marshal.loads = pickle.loads
marshal.dumps = pickle.dumps
# end

import os
import cgi
import datetime
import wsgiref.handlers
#import logging

from model import DataBaseOperations, Forum, Thread, Topic, Post, UserObj, File
from functions import strip_ml_tags, reverse_postmarkup
from postmarkup import *

from google.appengine.ext.db import *
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.api import mail
from google.appengine.ext.webapp.util import login_required
from google.appengine.api import images # for avatar
from django.core.paginator import ObjectPaginator, InvalidPage
# XMPP, google talk support
from google.appengine.api import xmpp
#from google.appengine.ext import admin

import mimetypes

# Full text search libraries:

from whoosh import store
from whoosh.fields import Schema, STORED, ID, KEYWORD, TEXT
from whoosh.index import getdatastoreindex
from whoosh.qparser import QueryParser, MultifieldParser

SEARCHSCHEMA = Schema(body=TEXT(stored=True))

logging.getLogger().setLevel(logging.DEBUG)


class AclUser:
  __admin__ = ['itishbi']
  
  __nickname = None
  
  def createUrl(self, uri):
    if self.user is not None:
      return users.CreateLogoutURL(uri)
    else:
      return users.CreateLoginURL(uri)
      
  def createLink(self):
    if self.user is not None:
      return 'Sign Out'
    else:
      return 'Sign In'
  
  def getNickname(self):
    return self.__nickname
  
  def getAuthentificatedUser(self):
    self.user = users.get_current_user()
    if not self.user:
      #self.redirect(users.create_login_url(self.request.uri))
      self.__nickname = 'Guest'
      return None
    self.__nickname = self.user.nickname()
    return self.user
  
  def checkIfAuthentificatedUserIsAdmin(self):
    self.user = users.get_current_user()
    if users.is_current_user_admin():
      return True
    try:
      pos = self.__admin__.index(str(users.get_current_user()))
      return True
    except ValueError:
      pass
    return False
    #return str(users.get_current_user()) == self.__admin__
  
  def checkMode(self, mode):
    return self.checkIfAuthentificatedUserIsAdmin() and mode == 'admin'

class Install(webapp.RequestHandler, AclUser, DataBaseOperations):
  @login_required
  def get(self):
    if not self.checkIfAuthentificatedUserIsAdmin():
      return
    forum = self.getForumInstance()
    if forum is not None:
      title = forum.title
      description = forum.description
    else:
      title = None
      description = None
    template_values = {
      'title': title,
      'description': description,
    }
    path = os.path.join(os.path.dirname(__file__), os.path.join('templates', 'manageForum.htm'))
    self.response.out.write(template.render(path, template_values))
    
  def post(self):
    if not self.checkIfAuthentificatedUserIsAdmin():
      return
    self.updateForumInstance(self.request.get('title'), self.request.get('description'))
    self.redirect('/?mode=admin')
        
class DeleteTopic(webapp.RequestHandler, AclUser):
  @login_required
  def get(self):
    if not self.checkIfAuthentificatedUserIsAdmin():
      return
    try:
      id = self.request.get('id')
      topic = Topic.get(db.Key.from_path('Topic', int(id)))
      thread_id = topic.thread.key().id()
      topic.delete()
    except:
      pass
    self.redirect('/viewThread?mode=admin&id='+str(thread_id))
    
    
class AddTopic(webapp.RequestHandler, AclUser, DataBaseOperations):
  def get(self):
    if self.getAuthentificatedUser() is not None:
      id = self.request.get('id')
      template_values = {
        'id': id,
      }
      path = os.path.join(os.path.dirname(__file__), os.path.join('templates', 'addTopic.htm'))
      self.response.out.write(template.render(path, template_values))
    else:
      self.response.out.write('You have not permission to add new topics. Please sign in first .')
  
  def post(self):
    user = self.getAuthentificatedUser()
    if not user:
      return
    id = self.request.get('id')
    try:
      thread = Thread.get(db.Key.from_path('Thread', int(id)))
    except:
      return
    name = strip_ml_tags(self.request.get('name'))
    if name == '':
      template_values = {
        'topics' : self.topics,
        'name' : name,
      }
    else:
      topic = Topic() #parent=thread
      topic.thread = thread
      topic.name = name
      if users.get_current_user():
        topic.author = users.get_current_user()
      topic.put()
      mode = self.request.get('mode')
      self.redirect('/view?id=' + str(topic.key().id()))
      return 
      template_values = {
        'topics' : self.topics,
        'name' : '',
      }
    path = os.path.join(os.path.dirname(__file__), os.path.join('templates', 'addTopic.htm'))
    self.response.out.write(template.render(path, template_values))
    
class ViewTopic(webapp.RequestHandler, AclUser, DataBaseOperations):
  #@login_required
  def get(self):
    user = self.getAuthentificatedUser()
    forum = self.getForumInstance()
    page = self.request.get('page')
    try:
      page = int(page) - 1
    except:
      page = 0
    try:
      id = int(self.request.get('id'))
      #topic = Topic.get(db.Key.from_path('Topic', id))
      topic = self.getTopic(id)
      # is this a private topic 
      if not topic.thread.public and user is None:
        self.redirect('/')
        return
    except:
      self.redirect('/')
      return
      #topic = self.getTopics().order('-pub_date').fetch(1)
      #topic = topic[0]
      #id = topic.key().id()
    posts = self.getPosts(id)
    paginator = ObjectPaginator(posts, 10)
    if page >= paginator.pages or page < 0:
      page = paginator.pages - 1
    if page >= paginator.pages - 1: 
      next = None
    else:
      next = page + 2
    if page < 1:
      prev = None
    else:
      prev = page
    template_values = {
      'url' : self.createUrl(self.request.uri),
      'link' : self.createLink(),
      'user' : self.getNickname(),
      'forum' : forum,
      'topic' : topic,
      'posts' : paginator.get_page(page),
      'pages' : range(1, paginator.pages + 1),
      'page' : page+1,
      'next' : next,
      'prev' : prev,
      
    }
    try:
      if self.checkMode(str(self.request.get('mode'))):
        path = os.path.join(os.path.dirname(__file__), os.path.join('templates', 'viewTopicAdminMode.htm'))
        self.response.out.write(template.render(path, template_values))
        return
    except:
      pass
    path = os.path.join(os.path.dirname(__file__), os.path.join('templates', 'viewTopic.htm'))
    self.response.out.write(template.render(path, template_values))    
    
class View(webapp.RequestHandler, AclUser, DataBaseOperations):
  #@login_required
  def get(self):
    user = self.getAuthentificatedUser()
    forum = self.getForumInstance()
    threads = self.getThreads().order('position')
    #Thread.all().order('position')
    template_values = {
      'admin': self.checkIfAuthentificatedUserIsAdmin(),
      'url' : self.createUrl(self.request.uri),
      'link' : self.createLink(),
      'user' : self.getNickname(),
      'forum' : forum,
      'threads' : threads,
    }
    try:
      if self.checkMode(str(self.request.get('mode'))):
        #self.response.headers.add_header('Set-Cookie', 'mode=%s; expires=Fri, 31-Dec-2020 23:59:59 GMT' % 'admin')
        path = os.path.join(os.path.dirname(__file__), os.path.join('templates', 'viewForumAdminMode.htm'))
        self.response.out.write(template.render(path, template_values))
        return
    except:
      pass
    path = os.path.join(os.path.dirname(__file__), os.path.join('templates', 'viewForum.htm'))
    self.response.out.write(template.render(path, template_values))
    
class SaveThreadPosition(webapp.RequestHandler, AclUser):
  def post(self):
    if self.checkIfAuthentificatedUserIsAdmin():
      for key, value in self.request.POST.items():
        if key[0:7] == "thread_":
          try:
            thread = Thread.get(db.Key.from_path('Thread', int(key[7:])))
            thread.position = int(value)
            thread.public = self.request.POST.has_key('public_'+key[7:])
            thread.put()
          except:
            pass
    self.redirect('/?mode=admin')
    
    
class AddNewThread(webapp.RequestHandler, AclUser):
  def post(self):
    if self.checkIfAuthentificatedUserIsAdmin():
      name = strip_ml_tags(self.request.get('name'))
      if name != '':
        thread = Thread()
        thread.name = name
        thread.position = int(self.request.get('position'))
        thread.put()
    self.redirect('/?mode=admin')
    
class ModifyThread(webapp.RequestHandler, AclUser):
  @login_required
  def get(self):
    id = int(self.request.get('id'))
    thread = Thread.get(db.Key.from_path('Thread', int(id)))
    template_values = {
      'thread' : thread,
    }
    path = os.path.join(os.path.dirname(__file__), os.path.join('templates', 'modifyThread.htm'))
    self.response.out.write(template.render(path, template_values))
    
  def post(self):
    if self.checkIfAuthentificatedUserIsAdmin():
      id = int(self.request.get('id'))
      try:
        thread = Thread.get(db.Key.from_path('Thread', int(id)))
        name = strip_ml_tags(self.request.get('name'))
        if name != '':
          thread.name = name
          thread.put()
      except:
        pass
    self.redirect('/?mode=admin')
    
class DeleteThread(webapp.RequestHandler, AclUser):
  def get(self):  
    if not self.checkIfAuthentificatedUserIsAdmin():
      return
    try:
      id = int(self.request.get('id'))
      thread = Thread.get(db.Key.from_path('Thread', id))
      thread.delete()
    except:
      pass
    self.redirect('/?mode=admin')
    
class DeletePost(webapp.RequestHandler, AclUser):
  def get(self):
    if not self.checkIfAuthentificatedUserIsAdmin():
      return
    try:
      id = str(self.request.get('id'))
      topicId = str(self.request.get('topic_id'))
      page = str(self.request.get('page'))
      post = Post.get(db.Key.from_path('Post', int(id)))
      post.delete()
    except:
      pass
    self.redirect('/view?mode=admin&id='+topicId+'&page='+page)
    
    
class ViewThread(webapp.RequestHandler, AclUser, DataBaseOperations):
  #@login_required
  def get(self):
    user = self.getAuthentificatedUser()
    forum = self.getForumInstance()
    try:
      id = int(self.request.get('id'))
      #thread = Thread.get(db.Key.from_path('Thread', id))
      thread = self.getThread(id)
      # is this a private topic 
      if not thread.public and user is None:
        self.redirect('/')
        return
    except:
      #thread = Thread.all().order('position').fetch(1)
      thread = self.getThreads().order('position').fetch(1)
      thread = thread[0]
      id = thread.key().id()
    topics = self.getTopics(id).order('pub_date')
    template_values = {
      'admin': self.checkIfAuthentificatedUserIsAdmin(),
      'url' : self.createUrl(self.request.uri),
      'link' : self.createLink(),
      'user' : self.getNickname(),
      'forum' : forum,
      'thread' : thread,
      'topics' :topics,
    }
    try:
      if self.checkMode(str(self.request.get('mode'))):
        #self.response.headers.add_header('Set-Cookie', 'mode=%s; expires=Fri, 31-Dec-2020 23:59:59 GMT' % 'admin')
        path = os.path.join(os.path.dirname(__file__), os.path.join('templates', 'viewThreadAdminMode.htm'))
        self.response.out.write(template.render(path, template_values))
        return
    except:
      pass
    path = os.path.join(os.path.dirname(__file__), os.path.join('templates', 'viewThread.htm'))
    self.response.out.write(template.render(path, template_values))
    
class EditPost(webapp.RequestHandler, AclUser, DataBaseOperations):
  """Edit Post Class"""
  def get(self):
    user = self.getAuthentificatedUser()
    if not user:
      return
    try:
      id = int(self.request.get('id'))
      post = Post().get(db.Key.from_path('Post', id))
      if post.author != user:
        self.redirect('/')
        return
      forum = self.getForumInstance()
      body = reverse_postmarkup(post.body)
      template_values = {
        'url' : users.CreateLogoutURL(self.request.uri),
        'user' : user.nickname(),
        'forum' : forum,
        'topic' : post.topic,
        'post' : post,
        'body' : body,
      }
      path = os.path.join(os.path.dirname(__file__), os.path.join('templates', 'editPost.htm'))
      self.response.out.write(template.render(path, template_values))      
    except:
      pass
    
  def post(self):
    user = self.getAuthentificatedUser()
    if not user:
      return
    try:
      id = int(self.request.get('post_id'))
      post = Post().get(db.Key.from_path('Post', id))
      if post.author != user:
        self.redirect('/')
        return
      body = db.Text(strip_ml_tags(self.request.get('body')))
      postmarkup = create(use_pygments=False)
      post.body = postmarkup(body)
      # replace('\n','<br />')
      if post.body != '':
        post.put()
          # re-index it!
        ix = getdatastoreindex("post_"+str(post.key().id()), schema=SEARCHSCHEMA)
        writer = ix.writer()
        writer.add_document(body=u"%s" % post.body)
        writer.commit()   
    except:
      pass
 
    if self.request.get('page'):
      self.redirect('/view?id=' + str(self.request.get('id')) + '&page=' + self.request.get('page'))
    else:
      self.redirect('/view?id=' + str(self.request.get('id')))
      

class AddPost(webapp.RequestHandler, AclUser, DataBaseOperations):
  """Add New Post Method"""
  def post(self):
    user = self.getAuthentificatedUser()
    if not user:
      return
    try:
      id = int(self.request.get('id'))
      topic = Topic().get(db.Key.from_path('Topic', id))
      preview = self.request.get('preview', None)
      if preview is not None:
        forum = self.getForumInstance()
        postmarkup = create(use_pygments=False)
        body = strip_ml_tags(self.request.get('body'))
        body2 = postmarkup(body)
        template_values = {
          'url' : users.CreateLogoutURL(self.request.uri),
          'user' : user,
          'forum' : forum,
          'topic' : topic,
          'body' : body,
          'body2' : body2,
          'page' : 100
        }
        path = os.path.join(os.path.dirname(__file__), os.path.join('templates', 'previewPost.htm'))
        self.response.out.write(template.render(path, template_values))
        return
    except:
       self.redirect('/')
       return
    post = Post() #parent=topic.key()
    post.topic = topic
    if users.get_current_user():
      post.author = users.get_current_user()
    body = db.Text(strip_ml_tags(self.request.get('body')))
    postmarkup = create(use_pygments=False)
    post.body = postmarkup(body)
    # replace('\n','<br />')
    if post.body != '':
      post.put()
      # index it!
      ix = getdatastoreindex("post_"+str(post.key().id()), schema=SEARCHSCHEMA)
      writer = ix.writer()
      writer.add_document(body=u"%s" % post.body)
      writer.commit()
      # end index
      mailAdditionalText = """ ... testing e-mail notification. Sorry if you get this message accidently."""
      post.sendMailToAll(user.email(), mailAdditionalText)
      #####
      #message = mail.EmailMessage(sender=user.email(), subject="New message in small-forum")
      #message.to = "log1 (sms) <48693781332@text.plusgsm.pl>"
      #message.body = post.body
      #message.send()
      #####
    # To Do
    if self.request.get('page'):
      self.redirect('/view?id=' + str(self.request.get('id')) + '&page=' + self.request.get('page'))
    else:
      self.redirect('/view?id=' + str(self.request.get('id')))
    
class Profile(webapp.RequestHandler, AclUser, DataBaseOperations):
  """user profile class"""
  def __init__(self):
    self.user = self.getAuthentificatedUser()
    
  @login_required
  def get(self):
    user = self.getAuthentificatedUser()
    forum = self.getForumInstance()
    userData = self.getUser(self.user)
    template_values = {
      'url' : users.CreateLogoutURL(self.request.uri),
      'link' : self.createLink(),
      'forum' : forum,
      'user' : self.user.nickname(),
      'name' : userData.name,
      'lastName' : userData.lastName,
      'from' : userData.cameFrom,
      'webpage' : userData.webpage,
      'mailing' : userData.mailing,
    }    
    path = os.path.join(os.path.dirname(__file__), os.path.join('templates', 'myProfile.htm'))
    self.response.out.write(template.render(path, template_values))
  
  def post(self):
    user = self.getAuthentificatedUser()
    if not user:
      return
    userData = self.getUser(self.user)
    userData.name = strip_ml_tags(self.request.get('name'))
    userData.lastName = strip_ml_tags(self.request.get('lastName'))
    userData.cameFrom = strip_ml_tags(self.request.get('from'))
    userData.webpage = self.request.get('webpage')
    mailing = str(self.request.get('mailing'))
    if mailing == "true":
      userData.mailing = True
    else:
      userData.mailing = False
    if self.request.get('avatar'):
      try:
        avatar = db.Blob(images.resize(self.request.get('avatar'), 100, 100))
        userData.avatar = avatar
      except:
        pass
    userData.put()
    self.redirect('/myProfile')
  
class Avatar(webapp.RequestHandler, AclUser, DataBaseOperations):
  def get(self):
    if self.request.get('user'):
      userData = self.getUser(users.User(self.request.get('user'))) # !!! + '@gmail.com'
    else:
      self.user = self.getAuthentificatedUser()
      userData = self.getUser(self.user)
    if userData.avatar:
      import datetime
      lastmod = datetime.datetime.now() 
      self.response.headers['Content-Type'] = "image/png"
      self.response.headers['Cache-Control']= 'public, max-age=172800'
      self.response.headers['Last-Modified'] = lastmod.strftime("%a, %d %b %Y %H:%M:%S GMT")
      expires = lastmod + datetime.timedelta(days=365)
      self.response.headers['Expires'] = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")     
      self.response.out.write(userData.avatar)
    else:
      self.redirect('/images/noavatar.png')
      
class ViewProfile(webapp.RequestHandler, AclUser, DataBaseOperations):
  """show user profile"""
  def get(self):   
    if self.getAuthentificatedUser() is not None and self.request.get('user'):
      try:
        userData = self.getUser(users.User(self.request.get('user'))) # !!! + '@gmail.com'
        template_values = {
          'login' : userData.login,
          'name' : userData.name,
          'lastName' : userData.lastName,
          'from' : userData.cameFrom,
          'webpage' : userData.webpage,
        }
        path = os.path.join(os.path.dirname(__file__), os.path.join('templates', 'viewProfile.htm'))
        self.response.out.write(template.render(path, template_values))  
      except:
        return
    else:
      self.response.out.write('You have not permission to see this profile. Please sign in first using google account.')
    
class RSSFeedHandler(webapp.RequestHandler, DataBaseOperations):
  def get(self):
    try:
      n = int(self.request.get('n'))
    except:
      n = 20
    forum = self.getForumInstance()
    posts = self.getLastPosts(n)
    try:
      for post in posts:
        post.body = strip_ml_tags(post.body)
    except:
      pass
    template_values = {
      'forum' : forum,
      'selfurl' : self.request.host_url,
      'posts' : posts,
    }
    self.response.headers['Content-Type'] = 'text/xml'
    path = os.path.join(os.path.dirname(__file__), os.path.join('templates', 'rss2.xml'))
    self.response.out.write(template.render(path, template_values))
    
class ViewAllUsers(webapp.RequestHandler, AclUser, DataBaseOperations):
  """View All Forum Users"""
  @login_required
  def get(self):
    user = self.getAuthentificatedUser()
    page = self.request.get('page')
    try:
      page = int(page) - 1
    except:
      page = 0
    allUsers = self.getUsers().order('login')
    paginator = ObjectPaginator(allUsers, 50)
    if page >= paginator.pages or page < 0:
      page = paginator.pages - 1
    if page >= paginator.pages - 1: 
      next = None
    else:
      next = page + 2
    if page < 1:
      prev = None
    else:
      prev = page
    
    forum = self.getForumInstance()
    template_values = {
      'url' : users.CreateLogoutURL(self.request.uri),
      'user' : user.nickname(),
      'forum' : forum,
      'users' : paginator.get_page(page),
      'pages' : range(1, paginator.pages + 1),
      'page' : page+1,
      'next' : next,
      'prev' : prev,
    }
    #for user in self.getUsers().order('-login'):
      #print user.login
    path = os.path.join(os.path.dirname(__file__), os.path.join('templates', 'viewUsers.htm'))
    self.response.out.write(template.render(path, template_values))
    
class PrivateMessage(webapp.RequestHandler, AclUser, DataBaseOperations):
  """Allow to send private message to users using google talk"""
  @login_required
  def get(self):
    jid = self.request.get('jid')
    template_values = {
      'jid' : jid,
    }
    path = os.path.join(os.path.dirname(__file__), os.path.join('templates', 'privateMessageForm.htm'))
    self.response.out.write(template.render(path, template_values))
   
    
  def post(self):
    user = self.getAuthentificatedUser()
    if not user: return
    jid = self.request.get('jid')
    # check if jid ends with 'gmail.com'
    if jid[-10:] != '@gmail.com':
      return
    body = strip_ml_tags(self.request.get('body'))
    if jid != '' and body != '':
      end = """
            .
            This message was sent using small forum for GAE form
            http://small-forum.appspot.com/
            """
      body += end
      sender = user.email()
      try:
        if sender[-10:] == '@gmail.com':
          xmpp.send_message(jid, body)
        else:
          xmpp.send_message(jid, body, from_jid=sender)
      except:
        print 'error'
      print 'OK, done'
      # To Do: normal redirect
    
  
class Test(webapp.RequestHandler):
  def get(self):
    
    '''
    posts = Post.all()
    for post in posts:
      self.response.out.write(post.body)
      #self.response.out.write('----------------------------')
      ix = getdatastoreindex("post_"+str(post.key().id()), schema=SEARCHSCHEMA)
      writer = ix.writer()
      writer.add_document(body=u"%s" % post.body)
      writer.commit()
      self.response.out.write('----------done indexed--------------')
    '''  
    '''
    #xmpp.send_invite('phphtmlcreator@gmail.com')
    status = xmpp.get_presence('phphtmlcreator@gmail.com')
    print 'status = ' + str(status)
    #xmpp.send_message('phphtmlcreator@gmail.com', 'hello' + str(status))
    print '------------------'
    return
    '''
  
class SearchForm(webapp.RequestHandler, DataBaseOperations):
  @login_required
  def get(self):
    template_values = {
      'threads' : self.getThreads(),
    }
    path = os.path.join(os.path.dirname(__file__), os.path.join('templates', 'searchForm.htm'))
    self.response.out.write(template.render(path, template_values))
    
class SearchResults(webapp.RequestHandler, AclUser, DataBaseOperations):
  
  def __init__(self):
    # list for search results - posts keys
    self.postKeys = list()
  
  def searchTextInTopic(self, entity, whatTextSearchFor):
    postKeys = []
    for post in entity.posts:
      ix = getdatastoreindex("post_"+str(post.key().id()), schema=SEARCHSCHEMA)
      parser = QueryParser("body", schema = ix.schema)
      q = parser.parse(whatTextSearchFor)
      results = ix.searcher().search(q)
      for result in results:
        if result['body'] != '':
          postKeys.append(post)
          break
    return postKeys
  
  def post(self):
    user = self.getAuthentificatedUser()
    forum = self.getForumInstance()
    whatTextSearchFor = strip_ml_tags(self.request.get('text'))
    whereSearch = self.request.get('where')
    #self.response.out.write(whatTextSearchFor + ' .. ' + str(whereSearch))
    # where to find results? in fourm, thread or single topic
    # can i do it simpler ?  
    kind = None
    if int(whereSearch) == 0:
      kind = 'Forum'
    if not kind:
      try:
        baseEntity = db.get(db.Key.from_path('Thread', int(whereSearch)))
        kind = baseEntity.kind()
      except:
        pass
    if not kind:
      try:
        baseEntity = db.get(db.Key.from_path('Topic', int(whereSearch)))
        kind = baseEntity.kind()
      except:
        pass
    #self.response.out.write(kind)
    if kind == 'Topic':
      self.postKeys = self.searchTextInTopic(baseEntity, whatTextSearchFor)
    elif kind == 'Thread':
      for topic in baseEntity.topics:
        self.postKeys.extend(self.searchTextInTopic(topic, whatTextSearchFor))
    else:
      # search whole forum
      for thread in self.getThreads():
        for topic in thread.topics:
          self.postKeys.extend(self.searchTextInTopic(topic, whatTextSearchFor))
    #self.response.out.write(self.postKeys)
    #posts = list()
    #for key in self.postKeys:
      #x = Post.get(db.Key.from_path('Post', int(key)))
      #print x.kind()
      #posts.append(Post.get(db.Key.from_path('Post', int(key))))
    #print posts
    template_values = {
      'url' : users.CreateLogoutURL(self.request.uri),
      'user' : user.nickname(),
      'forum' : forum,
      'results' : self.postKeys,
    }
    path = os.path.join(os.path.dirname(__file__), os.path.join('templates', 'viewSearchResults.htm'))
    self.response.out.write(template.render(path, template_values))
        
    '''search in topic only
      for post in baseEntity.posts:
      ix = getdatastoreindex("post_"+str(post.key().id()), schema=SEARCHSCHEMA)
      parser = QueryParser("body", schema = ix.schema)
      q = parser.parse(whatTextSearchFor)
      results = ix.searcher().search(q)
      for result in results:
        print result['body']
      #self.response.out.write(post.body + '....  ')
    '''
    
class FilesList(webapp.RequestHandler, AclUser, DataBaseOperations):
  
  @login_required
  def get(self):
    user = self.getAuthentificatedUser()
    forum = self.getForumInstance()
    files = File.all()
    template_values = {
      'url' : users.CreateLogoutURL(self.request.uri),
      'user' : user.nickname(),
      'forum' : forum,
      'files' : files,
    }
    path = os.path.join(os.path.dirname(__file__), os.path.join('templates', 'filesList.htm'))
    self.response.out.write(template.render(path, template_values))
    
  def post(self):
    try:
      file = self.request.get('file') #images.resize(self.request.get("img"), 64, 64)
      fileName = self.request.body 
      fileObj = File()
      fileObj.name = fileName[fileName.rfind('+%27')+4:fileName.rfind('%27')]
      fileObj.content = db.Blob(file)
      fileObj.owner = users.get_current_user()
      fileObj.put()
      self.redirect('/filesList')
    except RequestTooLargeError:
      self.response.out.write('The file:%s is too big! File size should me < 1MB' % fileObj.name)
    except:
      self.response.out.write('Sorry. There was an error(?)')
      
    
class GetFile(webapp.RequestHandler, AclUser, DataBaseOperations):
  def get(self, id, name='some_file.bin'):
    #try:
    id = int(id) #int(self.request.get('id'))
    file = File.get(db.Key.from_path('File', id))
      #if file.content:
    file.incrementDownloadCount()
    import datetime
    lastmod = datetime.datetime.now() 
    self.response.headers['Content-Type'] = "application/octet-stream"
    #self.response.headers['Cache-Control']= 'public, max-age=172800'
    #self.response.headers['Last-Modified'] = lastmod.strftime("%a, %d %b %Y %H:%M:%S GMT")
    #expires = lastmod + datetime.timedelta(days=365)
    #self.response.headers['Expires'] = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
    self.response.headers['Content-disposition'] = 'attachment; filename="%s"' % str(file.name)
    self.response.out.write(file.content)
        #self.response.headers['Cache-Control'] = "public, max-age=31536000"
        #self.response.headers['Content-Type'] = str(media_object.guessed_type)
    #except:
    #  self.response.out.write('Sorry, There is no such file')
    #last_modified_string = media_object.creation.strftime("%a, %d %b %Y %H:%M:%S GMT")
    #self.response.headers['Cache-Control'] = "public, max-age=31536000"
    #self.response.headers['Content-Type'] = str(media_object.guessed_type)
    #self.response.headers['Last-Modified'] = last_modified_string
    #expires = media_object.creation + datetime.timedelta(days=30)
    #self.response.headers['Expires'] = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
    pass
    
application = webapp.WSGIApplication([
  ('/', View),
  ('/viewThread', ViewThread),
  ('/manage', Install),
  ('/view', ViewTopic),
  ('/addTopic', AddTopic),
  ('/delTopic', DeleteTopic),
  ('/addPost', AddPost),
  ('/delPost', DeletePost),
  ('/editPost', EditPost),
  ('/manageForum', Install),
  ('/myProfile', Profile),
  ('/viewProfile', ViewProfile),
  ('/avatar', Avatar),
  ('/saveThreadPosition', SaveThreadPosition),
  ('/addNewThread', AddNewThread),
  ('/modifyThread', ModifyThread),
  ('/delThread', DeleteThread),
  ('/viewUsers', ViewAllUsers),
  ('/rss.xml', RSSFeedHandler),
  ('/prvateMessage', PrivateMessage),
  ('/searchForm', SearchForm),
  ('/searchResults', SearchResults),
  ('/filesList', FilesList),
  #(r'/getFile/(.*)', GetFile),
  (r'/getFile/(.*)/(.*)', GetFile),
  ('/test', Test),
], debug=True)


def main():
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
