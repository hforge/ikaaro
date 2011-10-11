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
    $(location).attr('href', link);
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
    $(location).attr('href', link);
    return false;
  });
});

function update_rrule_parameters(){
  /* Hide parameter "interval" on empty value and working_days */
  if ($("#rrule").val() == "" || $("#rrule").val() == "on_working_days" ){
      /* Hide parameters fields */
      $(".block-widget-rrule_interval").hide();
  }
  else {
      $(".block-widget-rrule_interval").show();
  };

  /* Show parameter "byday" only on weekly value */
  if ($("#rrule").val() == "weekly"){
      $(".block-widget-rrule_byday").show();
  }
  else {
      $(".block-widget-rrule_byday").hide();
  };
};
