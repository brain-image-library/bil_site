function loadSpinner() {
  var modalEl = document.getElementById('loadMe');
  var loadModal = bootstrap.Modal.getOrCreateInstance(modalEl, {
    backdrop: 'static',
    keyboard: false
  });
  loadModal.show();
}
