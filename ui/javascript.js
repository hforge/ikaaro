
/* Browse: select all/none */
function select_checkboxes(elt, checked) {
  var form = $(elt).parents('form');
  form.find('table input:checkbox').each(function() {
    $(this).attr('checked', checked);
  });
}


/* Popup */
var popup_window;
function popup(url, width, height) {
  // try-catch for IE
  try {
    if (popup_window != undefined && popup_window.closed == false)
      popup_window.close();
  } catch (ex) { }
  options = "menubar=no, status=no, scrollbars=yes, resizable=yes, width=" + width + ", height=" + height;
  popup_window = window.open(url, 'itools_popup', options);
  return false;
}


/* For the addlink/addimage popups */
function tabme_show(event) {
  event.preventDefault();
  $(".tabme a").each(function() {
    $(this.hash).hide(); // Hide all divs
    $(this).removeClass("selected"); // Remove flag
  });
  $(this.hash).show('fast'); // Show selected div
  $(this).addClass("selected"); // Add flag
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
    $("a[hash=" + hash + "]").addClass("selected"); // Select the matching tab
    tabs.click(tabme_show); // Hook the onclick event
  }
}


/* IE6-7 Fix button */
$(document).ready(function() {
    if ($.browser.msie && $.browser.version.substr(0,1) < 8) {
        var elements, element = null;

        for (i=0; i<document.forms.length; i++) {
            elements = document.forms[i].elements;
            var buttons = new Array();
            for (j=0; j<elements.length; j++) {
                element = elements[j];
                if (element.tagName == 'BUTTON' && element.getAttribute("name") == "action") {
                    buttons.push(element);
                }
            }
            // Do not hack form if there is only one button
            if (buttons.length > 1) {
                for (k=0; k<buttons.length; k++) {
                    // FIXME Remove already set click functions
                    buttons[k].onclick = function () {
                        for(l=0; l<this.form.elements.length; l++) {
                            if( this.form.elements[l].tagName == 'BUTTON' )
                                this.form.elements[l].disabled = true;
                        }
                        this.disabled = false;
                        this.value = this.attributes.getNamedItem("value").nodeValue ;
                    }
                }
            }
        }
    }
});
