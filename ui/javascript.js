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


function tabme_show(event) {
    event.preventDefault();
    $(".tabme a").each(function() {
        // Hide all divs
        $(this.hash).hide();
        // Remove flag
        $(this).removeClass("selected");
    });
    // Show selected div
    $(this.hash).show('fast');
    // Add flag
    $(this).addClass("selected");
}


function tabme() {
    // Find a tab menu and hook it
    var tabs = $(".tabme a");
    if (tabs.length) {
        // Hide all divs at start
        tabs.each(function() { $(this.hash).hide(); });
        // But show a default one, the one in the URL first
        var hash = window.location.hash ? window.location.hash : tabs.eq(0).attr("hash");
        $(hash).show();
        // Select the matching tab
        $("a[hash=" + hash + "]").addClass("selected");
        // Hook the onclick event
        tabs.click(tabme_show);
    }
}
