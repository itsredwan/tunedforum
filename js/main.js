// CUSTOM JS SCRIPT FOR Very Small forum for GAE
// BB code handling
// (c) 2010 by log1 [log1@poczta.fm]
// GPL license 

$(document).ready(function() {

  $('#bb_b').click(function() {
    $('#body').val($('#body').val() + "[b][/b]");
  });
  
  $('#bb_i').click(function() {
    $('#body').val($('#body').val() + "[i][/i]");
  });
  
  $('#bb_u').click(function() {
    $('#body').val($('#body').val() + "[u][/u]");
  });
  
  $('#bb_quote').click(function() {
    $('#body').val($('#body').val() + "[quote][/quote]");
  });
  
  $('#bb_code').click(function() {
    $('#body').val($('#body').val() + "[code][/code]");
  });
  
  $('#bb_img').click(function() {
    text_prompt = 'http://';
    var inserttext = prompt("[img]xxx[/img]", text_prompt);
    if ((inserttext != null) && (inserttext != ""))
      $('#body').val($('#body').val() + "[img]"+inserttext+"[/img]");
  });
  
  $('#bb_url').click(function() {
    var linktext = prompt("Link name", "");
    var linkurl = prompt("Insert url here", "http://");
    if ((linkurl != null) && (linkurl != "")) {
      if ((linktext != null) && (linktext != "")) to_append = "[url="+linkurl+"]"+linktext+"[/url]";
      else to_append = "[url]"+linkurl+"[/url]";
      
      $('#body').val($('#body').val() + to_append);
    }
    
  });
  
  
  
  
  
});

