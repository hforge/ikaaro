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
}


/*
 * Insert image or link from popup
 */

function select_img(value, caption) {
  window.opener.insertTags('\n\n.. figure:: ' + value + '\n\n   ',
                           '\n\n', caption);
  window.close();
}

function select_link(value) {
  window.opener.insertTags('`', '`_', value, true);
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
