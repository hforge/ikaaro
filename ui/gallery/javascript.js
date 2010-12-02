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
