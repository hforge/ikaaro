function reply(id){
  var comment = document.getElementById('comment'+id).innerHTML;

  /* Replace html by text */
  var reg = new RegExp("(&gt;)", "g");
  comment = comment.replace(reg, '>');
  reg = new RegExp("(&lt;)", "g");
  comment = comment.replace(reg, '<');
  reg = new RegExp("(&amp;)", "g");
  comment = comment.replace(reg, '&');
  reg = new RegExp("(&nbsp;)", "g");
  comment = comment.replace(reg, ' ');
  reg1 = new RegExp('(<a href=")', "g");
  reg2 = new RegExp('(">.*</a>)', "g");
  if (comment.match(reg1) && comment.match(reg2)) {
      comment = comment.replace(reg1, '');
      comment = comment.replace(reg2, '');
  }

  comment = comment.split(/\r|\n/);
  replytext = ''
  for (var i=0; i < comment.length; i++){
    replytext += "> " + comment[i] + "\n";
  }
  replytext = "(In reply to comment #" + id + ")\n" + replytext + "\n";
  var textarea = document.getElementById('comment')
  textarea.value = replytext
  textarea.focus();
}

function update_tracker_list(list_name){
  $('#' + list_name).children().remove();
  var options = '' ;
  $('#product option:selected').each(function() {
    var id_product = $(this).val();
    for (var i=0; i < list_products[id_product][list_name].length; i++) {
     options += '<option value="';
     options += list_products[id_product][list_name][i]['id'] + '">';
     options += list_products[id_product][list_name][i]['value'];
     options += '</option>';
    }
  });
  $("#" + list_name).html(options);
}

function update_tracker(){
      update_tracker_list('version');
      update_tracker_list('module');
}

$(document).ready(function () {
  update_tracker();
  $("#product").bind("change", update_tracker);
});
