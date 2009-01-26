// MediaWiki JavaScript support function
// http://www.mediawiki.org/
// MediaWiki is licensed under GNU General Public License version 2 or later
// apply tagOpen/tagClose to selection in textarea,
// use sampleText instead of selection if there is none

function insertTags(tagOpen, tagClose, sampleText, target)
{
  var txtarea;
  if (document.editform) {
    txtarea = document.editform.data;
  } else {
    // some alternate form? take the first one we can find
    var areas = document.getElementsByTagName('textarea');
    txtarea = areas[0];
  }
  var selText, isSample = false;

  if (document.selection  && document.selection.createRange) {
    // IE/Opera

    //save window scroll position
    if (document.documentElement && document.documentElement.scrollTop)
      var winScroll = document.documentElement.scrollTop
    else if (document.body)
      var winScroll = document.body.scrollTop;
    //get current selection
    txtarea.focus();
    var range = document.selection.createRange();
    selText = range.text;
    //insert tags
    checkSelectedText();
    range.text = tagOpen + selText + tagClose;
    //insert link target
    if (isSample == false && target != undefined) {
        //reuse value as the target if asked
        if (target == true) {
            target = sampleText;
        }
        //find next empty line or at the end
        var returnStart = txtarea.value.indexOf('\n', startPos);
        if (returnStart == -1) {
            returnStart = txtarea.value.length;
        }
        txtarea.value = txtarea.value.substring(0, returnStart)
            + '\n\n.. _`' + selText + '`: ' + target
            + txtarea.value.substring(returnStart, txtarea.value.length)
            + '\n';
    }
    //mark sample text as selected
    if (isSample && range.moveStart) {
      if (window.opera)
        tagClose = tagClose.replace(/\n/g,'');
      range.moveStart('character', - tagClose.length - selText.length);
      range.moveEnd('character', - tagClose.length);
    }
    range.select();
    //restore window scroll position
    if (document.documentElement && document.documentElement.scrollTop)
      document.documentElement.scrollTop = winScroll
    else if (document.body)
      document.body.scrollTop = winScroll;

  }
  else if (txtarea.selectionStart || txtarea.selectionStart == '0') {
    // Mozilla

    //save textarea scroll position
    var textScroll = txtarea.scrollTop;
    //get current selection
    txtarea.focus();
    var startPos = txtarea.selectionStart;
    var endPos = txtarea.selectionEnd;
    selText = txtarea.value.substring(startPos, endPos);
    //insert tag
    checkSelectedText();
    txtarea.value = txtarea.value.substring(0, startPos)
      + tagOpen + selText + tagClose
      + txtarea.value.substring(endPos, txtarea.value.length);
    //insert link target
    if (isSample == false && target != undefined) {
        //reuse value as the target if asked
        if (target == true) {
            target = sampleText;
        }
        //find next empty line or at the end
        var returnStart = txtarea.value.indexOf('\n', startPos);
        if (returnStart == -1) {
            returnStart = txtarea.value.length;
        }
        txtarea.value = txtarea.value.substring(0, returnStart)
            + '\n\n.. _`' + selText + '`: ' + target
            + txtarea.value.substring(returnStart, txtarea.value.length)
            + '\n';
    }
    //set new selection
    if (isSample) {
      txtarea.selectionStart = startPos + tagOpen.length;
      txtarea.selectionEnd = startPos + tagOpen.length + selText.length;
    } else {
      txtarea.selectionStart = startPos + tagOpen.length + selText.length + tagClose.length;
      txtarea.selectionEnd = txtarea.selectionStart;
    }
    //restore textarea scroll position
    txtarea.scrollTop = textScroll;
  }
  //this function, as a macro, shares the same namespace
  function checkSelectedText() {
      if (!selText) {
          selText = sampleText;
          isSample = true;
      } else if (selText.charAt(selText.length - 1) == ' ') {
          //exclude ending space char
          selText = selText.substring(0, selText.length - 1);
          tagClose += ' '
      }
  }
  return false;
}

function wiki_bold() {
  return insertTags('**', '**', 'Bold Text');
}

function wiki_italic() {
  return insertTags('*', '*', 'Italic Text');
}

function wiki_bullist() {
  return insertTags('\n\n* ', '\n* \n', 'List Item');
}

function wiki_numlist() {
  return insertTags('\n\n1. ', '\n2. \n', 'List Item');
}

function wiki_link() {
  return popup('../;add_link?mode=wiki', 700, 480);
}

function wiki_image() {
  return popup('../;add_image?mode=wiki', 700, 480);
}

function wiki_table() {
  return insertTags('\n\n===== =====\n', '\n===== =====\n\n',
                    'Cell1 Cell2');
}

function wiki_format() {
  var formatselect = $("#data_formatselect");
  var offset = formatselect.offset();
  offset.top += formatselect.height();
  var menu = $("#data_formatselect_menu");
  menu.css(offset);
  menu.toggle('fast');
}

function wiki_preformatted() {
  $("#data_formatselect_menu").hide('fast');
  return insertTags('\n\n::\n\n  ', '\n\n',
                    'Type text not to interpret with identation');
}

function wiki_heading1() {
  $("#data_formatselect_menu").hide('fast');
  return insertTags('\n\n=====\n', '\n=====\n\n', 'Title');
}

function wiki_heading2() {
  $("#data_formatselect_menu").hide('fast');
  return insertTags('\n\n', '\n=====\n\n', 'Title');
}

function wiki_heading3() {
  $("#data_formatselect_menu").hide('fast');
  return insertTags('\n\n', '\n-----\n\n', 'Title');
}

function wiki_help() {
  return popup(';help?popup=1', 600, 400);
}


/*
 * Insert image or link from popup
 */

function select_element(type, value, caption) {
  if(type=='image'){
      window.opener.insertTags('\n\n.. figure:: ' + value + '\n\n   ',
                               '\n\n', caption);
  }else{
      window.opener.insertTags('`', '`_', value, true);
  }
  window.close();
}

function select_link(value) {
  window.close();
}

function select_uri() {
  var target = document.getElementById('uri').value;
  var start = target.indexOf('/') + 2;
  var stop = target.indexOf('/', start);
  if (stop == -1) {
    stop = target.length;
  }
  var value = target.substring(start, stop);
  window.opener.insertTags('`', '`_', value, target);
  window.close();
}


var Cookie = null;
$(document).ready(function() {
    try {
        Cookie = tinymce.util.Cookie;
    }
    catch (error) {
    }
});

function text_small() {
  $("#data").css("font-size", "1.2em");
  Cookie.set("wiki_text_size", "small");
  return false;
}

function text_medium() {
  $("#data").css("font-size", "1.4em");
  Cookie.set("wiki_text_size", "medium");
  return false;
}

function text_large() {
  $("#data").css("font-size", "1.6em");
  Cookie.set("wiki_text_size", "large");
  return false;
}


function setup_size() {
  size = Cookie.get("wiki_text_size");
  if (size) {
    if (size == "small")
      text_small();
    else if (size == "medium")
      text_medium();
    else if (size == "large")
      text_large();
  }
}


function setup_resize() {
  var handle = $("#data_resize");
  var editor = $("#data_table");
  var txtarea = $("#data");
  var ghost = $("#mcePlaceHolder");
  var body = $(document.body);
  var min_width = 100;
  var min_height = 100;
  var max_width = 0xFFFF;
  var max_height = 0xFFFF;
  var r = {x: null,
           y: null,
           w: null,
           h: null,
           dx: null,
           dy: null};
  var prefs = Cookie.getHash("wiki_data_size");
  if (prefs && prefs.ew && prefs.eh && prefs.th) {
    editor.width(Math.max(10, prefs.ew) + 'px');
    editor.height(Math.max(10, prefs.eh) + 'px');
    // XXX dont't set width!
    txtarea.height(Math.max(10, prefs.th) + 'px');
  }

  var trigger_mousemove = function(e) {
    // Calc delta values
    r.dx = e.screenX - r.x;
    r.dy = e.screenY - r.y;
    // Boundery fix box
    var w = Math.max(min_width, r.w + r.dx);
    var h = Math.max(min_height, r.h + r.dy);
    w = Math.min(max_width, w);
    h = Math.min(max_height, h);
    // Resize placeholder
    ghost.width(w + 'px');
    ghost.height(h + 'px');
    e.preventDefault();
  };

  var trigger_mouseup = function(e) {
    editor.show();
    ghost.hide();
    if (r.dx === null)
      return;
    var width = r.w + r.dx;
    var height = r.h + r.dy;
    editor.width(Math.max(10, width) + 'px');
    editor.height(Math.max(10, height) + 'px');
    // XXX dont't set width!
    txtarea.height(Math.max(10, txtarea.height() + r.dy) + 'px');
    // Remove triggers
    body.unbind("mousemove");
    body.unbind("mouseup");
    // Save actual size (not desired size!)
    Cookie.setHash("wiki_data_size", {ew: editor.width(),
                                      eh: editor.height(),
                                      th: txtarea.height()});
    e.preventDefault();
  };

  handle.mousedown(function(e) {
    // Measure container
    var w = editor.width();
    var h = editor.height();
    // Setup placeholder
    ghost.width(w);
    ghost.height(h);
    // Replace with placeholder
    editor.hide();
    ghost.show();
    // Initialize resize object
    r.x = e.screenX;
    r.y = e.screenY;
    r.w = w;
    r.h = h;
    // Add triggers
    body.mousemove(trigger_mousemove);
    body.mouseup(trigger_mouseup);
    e.preventDefault();
  });
}
