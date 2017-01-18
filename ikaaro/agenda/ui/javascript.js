$(document).ready(function(){

  // Hide add event buttons
  $(".add-event-area .add-event").hide();
  // Intercept clicks on events
  $(".event").click(function(e){
    var target  = $(e.target);
    if( target.is('a') ) {
      var link = target.attr('href');
    }else if( target.is('img') ) {
      var link = target.parent.attr('href');
    }else{
      var link = $(this).children('.event-link:first').attr('href');
    }
    open_in_fancybox(link);
    return false;
  });
  // Intercept clicks on add-event-area
  $(".add-event-area").click(function(e){
    var target  = $(e.target);
    if( target.is('img') ) {
      var link = target.parent.attr('href');
    }else{
      var link = $(this).children('.add-event').attr('href');
    }
    open_in_fancybox(link);
    return false;
  });

  // Open links as fancybox
  $("a[rel='fancybox']").click(function(e){
    open_in_fancybox(this.href);
    return false;
  });

});

function open_in_fancybox(url){
  $.fancybox({'type': 'iframe',
              'transitionIn': 'none',
              'transitionOut': 'none',
              'href': add_parameter_to_url(url, 'fancybox=1'),
              'overlayColor': '#333',
              'overlayOpacity': 0.8,
              'onClosed': function() {window.location.reload();},
              'hideOnOverlayClick': false,
              'width': 800,
              'height': 550,
              'centerOnScroll': true});

}

function update_rrule_parameters(){
  value = $("#rrule").val();
  /* Hide parameter "interval" on empty value */
  if (value == "") {
      /* Hide parameters fields */
      $(".block-widget-rrule_interval").hide();
      $(".block-widget-rrule_until").hide();
  }
  else {
      $(".block-widget-rrule_interval").show();
      $(".block-widget-rrule_until").show();
      /** Update label on span aside select field **/
      /* Hide any label */
      $(".rrule_interval-daily").hide();
      $(".rrule_interval-weekly").hide();
      $(".rrule_interval-monthly").hide();
      $(".rrule_interval-yearly").hide();
      /* Show selected label */
      $(".rrule_interval-"+value).show();
  };

  /* Show parameter "byday" only on weekly value */
  if (value == "weekly"){
      $(".block-widget-rrule_byday").show();
  }
  else {
      $(".block-widget-rrule_byday").hide();
  };
};
