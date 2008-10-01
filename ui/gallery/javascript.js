var images = new Array();
var images_array = new Array();
var images_loaded = new Array();
var current = 0;

/* load image, return 1 if image is finished loading */
function load(i) {
    if (images_loaded[i] == 0) {
        images_array[i] = new Image();
        unquoted = images[i].replace("&amp;", "&");
        images_array[i].src = unquoted;
        images_loaded[i] = 1;
    }
    if (images_loaded[i] == 1) {
        if (images_array[i].complete) {
            images_loaded[i] = 2;
        } else {
            return 0;
        }
    }
    return 1;
}


function preload() {
    load(current);

    // Load following ones
    for (current = current + 1; current < images.length; current++) {
        if (load(current) == 0) {
            // Not finished, check again later
            setTimeout("preload()", 50);
            return;
        }
    }
}


function preload_init() {
    for (i = 0; i < images.length; i++) {
        /* this array will contain 0 if image not yet loaded, 1 when loading,
         * 2 when complete */
        images_loaded[i] = 0;
        /* this array will contain loaded images */
        images_array[i] = null;
    }
    preload();
}


function apply_best_resolution(resolutions) {
    var available = $(window).width() - 30;
    var width = resolutions[resolutions.length - 1];
    for (i = 1; i < resolutions.length; i++) {
      if (available < resolutions[i]) {
        width = resolutions[i - 1];
        break;
      }
    }
    $(".thumbnail a").each(function() {
        if (!$(this).parents(".folder").length)
          if (window.location.search.indexOf("width=") == -1)
            this.href = this.href + '&width=' + width + '&height=' + width;
    });
}
