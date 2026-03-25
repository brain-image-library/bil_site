function loadSpinner() {
    var modalEl = document.getElementById('loadMe');
    var loadModal = bootstrap.Modal.getOrCreateInstance(modalEl, {
      backdrop: 'static',
      keyboard: false
    });
    loadModal.show();
    var url = "${window.origin}/ingest/descriptive_metadata_upload/";
    $.post(
      url,
      function(response) {
        if (response.data[0]) {
          //if you received a successful return, remove the modal. Either way remove the modal!!
          var resOutput =
            '<h4 style="color: black">Success!</h4>';
          $("#output").html(resOutput);
          loadModal.hide();
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
