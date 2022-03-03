function loadSpinner() {
    $("#loadMe").modal({
      backdrop: "static", //remove ability to close modal with click
      keyboard: false, //remove option to close with keyboard
      show: true //Display loader!
    });
    var url = "${window.origin}/ingest/descriptive_metadata_upload/";
    $.post(
      url,
      function(response) {
        if (response.data[0]) {
          //if you received a successful return, remove the modal. Either way remove the modal!!
          var resOutput =
            '<h4 style="color: black">Success!</h4>';
          $("#output").html(resOutput);
          $("#loadMe").modal("hide");
        } else {
          $("#output").html(
            '<div class="alert alert-warning"><h4>Please see the errors or contact BIL Support</h4></div>'
          );
        }
      },
      "json"
    );
  // });
};
