function collection_send() {
    let output_rows = []
    $('tbody>tr').each(function(i, e){
        let $e = $(e);
        // $e is the tr element
        let row_is_checked = $e.find('#collection_is_checked').is(':checked');
        // row_is_checked is a boolean of whether that row is checked or not
        let bil_uuid = $e.find('#bil')
        if(row_is_checked)
            output_rows.push({
                'billUuid': bil_uuid
                }
            )
    });
  fetch(window.origin + '/collection_send', {
      method: "POST",
      credentials: "include",
      body: JSON.stringify(output_rows),
      cache: "no-cache",
      headers: new Headers({
          "content-type": "application/json"
      })
  })
      .then(function(response) {
          if (response.status !== 200) {
              console.log('Looks like there was a problem. Status code: ${response.status}');
              return;
          }
              response.json().then(function(data) {
              console.log(data);
              window.location.replace(data['url']);
          });
      })
      .catch(function(error) {
          console.log("Fetch error: " + error);
  });
} 