/*
 * Insert image or link from popup
 */


function select_element(type, value, caption) {
    tiny_mce_set_uri_value(value);
}

function tiny_mce_set_uri_value(uri) {
    //call this function only after page has loaded
    //otherwise tinyMCEPopup.close will close the
    //"Insert/Edit Image" or "Insert/Edit Link" window instead

    var win = tinyMCEPopup.getWindowArg("window");
    // insert information now
    var input_name = tinyMCEPopup.getWindowArg("input");
    if (input_name == 'backgroundimage') {
        // replace semicolon by %3B
        // <table style="background-image: url(../fond-400x500/%3Bdownload);">
        var reg = new RegExp("(/;download)", "g");
        uri = uri.replace(reg, '/%3Bdownload');
    }
    win.document.getElementById(input_name).value = uri;
    // for image browsers: update image dimensions
    if (win.getImageData) win.getImageData();
    // close popup window
    tinyMCEPopup.close();
    win.focus();
}

/*
 * Use our own filebrowser
 */
function ikaaro_filebrowser(field_name, url, type, win) {
    var cms_location = unescape(window.location.href);

    // Strip the view
    var cms_index = cms_location.indexOf(';');
    var cms_base;
    if (cms_index == -1) {
        if (cms_location[cms_location.length - 1] == '/')
            cms_base = cms_location;
	else
	    cms_base = cms_location + '/';
    } else
        cms_base = cms_location.substring(0, cms_index);

    var cms_specific_action = ';add_link?mode=tiny_mce';
    if (type == 'image')
        cms_specific_action = ';add_image?mode=tiny_mce';
    else if (type == 'media')
        cms_specific_action = ';add_media?mode=tiny_mce';
    var cmsURL = cms_base + cms_specific_action;      // script URL

    tinyMCE.activeEditor.windowManager.open({
        file : cmsURL + "&type=" + type,
        width : 640,  // Your dimensions may differ - toy around with them!
        height : 480,
        resizable : "yes",
        inline : "no",  // This parameter only has an effect if you use the inlinepopups plugin!
        close_previous : "yes",
        scrollbars : "yes",
        popup_css : "false"
    }, {
        window : win,
        input : field_name,
        theme_url : 'none'
    });
    return false;
}
