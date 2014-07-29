import re

# Routine by Micah D. Cochran
# Submitted on 26 Aug 2005
# This routine is allowed to be put under any license Open Source (GPL, BSD, LGPL, etc.) License 
# or any Propriety License. Effectively this routine is in public domain. Please attribute where appropriate.

# Modified 13.03.2010 by log1
def strip_ml_tags(in_text, begin_tag='<', end_tag='>'):
  """Description: Removes all HTML/XML-like tags from the input text.
  Inputs: s --> string of text
  Outputs: text string without the tags
  
  # doctest unit testing framework
  
  >>> test_text = "Keep this Text <remove><me /> KEEP </remove> 123"
  >>> strip_ml_tags(test_text)
  'Keep this Text  KEEP  123'
  """
  # convert in_text to a mutable object (e.g. list)
  s_list = list(in_text)
  i,j = 0,0
  
  while i < len(s_list):
    # iterate until a left-angle bracket is found
    if s_list[i] == begin_tag:
      while s_list[i] != end_tag:
        # pop everything from the the left-angle bracket until the right-angle bracket
        s_list.pop(i)
      # pops the right-angle bracket, too
      s_list.pop(i)
    else:
      i=i+1
      
  # convert the list back into text
  join_char=''
  return join_char.join(s_list)

# temporary function
def reverse_postmarkup(text):
  """Transform HTML into BB code"""
  text = strip_ml_tags(text, '[', ']')
  text = text.replace('<strong>', '[b]')
  text = text.replace('</strong>', '[/b]')
  text = text.replace('<em>', '[i]')
  text = text.replace('</em>', '[/i]')
  text = text.replace('<u>', '[u]')
  text = text.replace('</u>', '[/u]')
  text = text.replace('<blockquote>', '[quote]')
  text = text.replace('</blockquote>', '[/quote]' )
  text = text.replace('<div class="code"><pre>', '[code]')
  text = text.replace('</pre></div>', '[/code]')
  text = re.sub(r'<img src="(.*?)"></img>', r'[img]\1[/img]', text)
  text = re.sub(r'<a href="http://(.*?)">(.*?)</a>', r'[url=\1]\2[/url]', text)
  text = text.replace(u"<br/>", u'\n')
  # just in case
  text = strip_ml_tags(text)
  return text
  
  


