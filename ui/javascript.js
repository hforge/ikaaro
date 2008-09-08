/* Browse: select all/none */
function select_checkboxes(form_id, checked) {
  $("#" + form_id + " INPUT[type='checkbox']").each( function(){
    $(this).attr('checked', checked);
  });
}

/* Popup */
var popup_window;
function popup(url, width, height) {
    // try catch for IE
    try {
        if (popup_window != undefined && popup_window.closed == false)
            popup_window.close();
    } catch (ex) {
        // do nothing
    }
    options = "menubar=no, status=no, scrollbars=yes, resizable=yes, width=" + width;
    options += ", height=" + height;
    popup_window = window.open(url, 'itools_popup', options);
    return false;
}
