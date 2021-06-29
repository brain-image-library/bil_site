function submit_user_changes() {
    const csrftoken = Cookies.get('csrftoken');
    let auth_id = document.getElementById("auth_id");
    console.log(auth_id)
    let output_rows = []
    $('tbody>tr').each(function(i, e){
        let $e = $(e);
        // $e is the tr element
        if($e.find('.modified').length>0){
            let is_pi = $e.find('#is_pi')
            let is_po = $e.find('#is_po')
            let is_bil_admin = $e.find('#is_bil_admin')
            output_rows.push({
            "project_id": $e.data('project_id'),
            "auth_id": auth_id.getAttribute('value'),
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
