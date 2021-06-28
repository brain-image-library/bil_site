function submit_user_changes() {
    const csrftoken = Cookies.get('csrftoken');
    let output_rows = []
    $('tbody>tr').each(function(i, e){
        const auth_id = document.getElementById("auth_id")
        let $e = $(e);
        // $e is the tr element
        //let row_is_checked = $e.find('#collection_is_checked').is(':checked');
        if($e.find('.modified').length>0){
	    //let auth_id = $e.find(#'auth_id')
            let is_pi = $e.find('#is_pi')
            let is_po = $e.find('#is_po')
            let is_bil_admin = $e.find('#is_bil_admin')
            output_rows.push({
            "auth_id": auth_id.value,
            "is_pi": is_pi.val(),
            "is_po": is_po.val(),
            "is_bil_admin": is_bil_admin.val()})
        }
             console.log(output_rows)
        
                
            
    });
  fetch(`${window.origin}/ingest/userModify/`, {
      method: "POST",
      credentials: "include",
      body: JSON.stringify(output_rows),
      cache: "no-cache",
      headers: new Headers({
          "X-CSRFToken": csrftoken,
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
