function change_bil_admin_privs() {
    const csrftoken = Cookies.get('csrftoken');
    const output_rows = [];
    const person_id = document.getElementById("person_id");
    const is_bil_admin = document.getElementById("is_bil_admin");

    output_rows.push({
        "person_id": person_id.getAttribute('value'),
        "is_bil_admin": is_bil_admin.value,
        })      
            
  fetch(`${window.origin}/ingest/change_bil_admin_privs/`, {
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
