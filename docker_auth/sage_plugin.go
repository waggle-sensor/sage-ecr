package main

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/cesanta/docker_auth/auth_server/api"
)

var (
	tokenInfoEndpoint string
	tokenInfoUser     string
	tokenInfoPassword string

	Authn SageAuthn
)

func init() {
	tokenInfoEndpoint = os.Getenv("tokenInfoEndpoint")
	tokenInfoUser = os.Getenv("tokenInfoUser")
	tokenInfoPassword = os.Getenv("tokenInfoPassword")

	if tokenInfoEndpoint == "" {
		log.Fatalf("Environment variable \"tokenInfoEndpoint\" not defined")
		return
	}

	if tokenInfoUser == "" {
		log.Fatalf("Environment variable \"tokenInfoUser\" not defined")
		return
	}

	if tokenInfoPassword == "" {
		log.Fatalf("Environment variable \"tokenInfoPassword\" not defined")
		return
	}
}

// AuthnX this implements the interface api.Authenticator from https://github.com/cesanta/docker_auth/blob/master/auth_server/api/authn.go
type SageAuthn struct {
}

// Authenticate _
func (sa *SageAuthn) Authenticate(user string, password api.PasswordString) (bool, api.Labels, error) {

	passwordString := string([]byte(password))

	err := SageAuthenticate(user, passwordString)

	if err != nil {
		return false, api.Labels{}, err
	}

	return true, api.Labels{}, nil
}

// Stop _
func (sa *SageAuthn) Stop() {
	return
}

// Name _
func (sa *SageAuthn) Name() string {
	return "SAGE Authenticator"
}

type TokenResponse struct {
	Active   bool   `json:"active"`
	Scope    string `json:"scope"`
	ClientID string `json:"client_id"`
	Username string `json:"username"`
	Exp      int    `json:"exp"`

	Error  string `json:"error"`
	Detail string `json:"detail"`
}

// SageAuthenticate Validate token, field user is not yet used
// user has to match the username (a uuid) returned by the token or match the "sage username" defined in the scope list
func SageAuthenticate(user string, tokenStr string) (err error) {

	url := tokenInfoEndpoint

	log.Printf("url: %s\n", url)
	log.Printf("tokenStr: %s\n", tokenStr)

	payload := strings.NewReader("token=" + tokenStr)
	client := &http.Client{
		Timeout: time.Second * 5,
	}
	req, err := http.NewRequest("POST", url, payload)
	if err != nil {
		log.Print("NewRequest returned: " + err.Error())
		//http.Error(w, err.Error(), http.StatusInternalServerError)
		err = fmt.Errorf("NewRequest returned: %s", err.Error())
		return
	}

	auth := tokenInfoUser + ":" + tokenInfoPassword
	//fmt.Printf("auth: %s\n", auth)
	authEncoded := base64.StdEncoding.EncodeToString([]byte(auth))
	req.Header.Add("Authorization", "Basic "+authEncoded)

	req.Header.Add("Accept", "application/json; indent=4")
	req.Header.Add("Content-Type", "application/x-www-form-urlencoded")

	res, err := client.Do(req)
	if err != nil {
		log.Print(err)
		//http.Error(w, err.Error(), http.StatusInternalServerError)

		err = fmt.Errorf("client.Do returned: %s", err.Error())
		return
	}
	defer res.Body.Close()
	body, err := ioutil.ReadAll(res.Body)
	if err != nil {
		//http.Error(w, err.Error(), http.StatusInternalServerError)

		err = fmt.Errorf("ioutil.ReadAll returned: %s", err.Error())
		return
	}

	dat := TokenResponse{}
	jsonErr := json.Unmarshal(body, &dat)

	log.Printf("dat.Username: %s\n", dat.Username)

	if res.StatusCode == 401 {
		err = api.WrongPass
		return
	}

	if res.StatusCode != 200 {
		fmt.Printf("%s", body)
		//http.Error(w, fmt.Sprintf("token introspection failed (%d) (%s)", res.StatusCode, body), http.StatusInternalServerError)

		if jsonErr == nil {

			if dat.Detail != "" {
				// error message from the Django framework

				//if dat.Detail == "Invalid username/password." {
				//	err = api.WrongPass
				//	return
				//}
				err = fmt.Errorf("token introspection failed (detail=%s)", dat.Detail)
				return
			}

			if dat.Error != "" {

				if dat.Error == "token not found" {
					err = api.WrongPass
					return
				}

				err = fmt.Errorf("error was returned: %s", dat.Error)
				return

			}

		}

		err = fmt.Errorf("token introspection failed (%d) (%s)", res.StatusCode, body)
		return
	}

	if jsonErr != nil {
		err = fmt.Errorf("json parsing failed: %s", err.Error())
		return
	}

	if dat.Error != "" { // should not happen if status==200
		err = fmt.Errorf("error was returned: %s", dat.Error)
		return
	}

	if !dat.Active {
		return api.WrongPass
	}

	if dat.Username != user {

		for _, scope := range strings.SplitAfter(dat.Scope, " ") {
			if strings.HasPrefix(scope, "sage_username:") {
				scopeUsername := strings.TrimPrefix(scope, "sage_username:")
				if user == scopeUsername {
					// success
					return
				}

			}
		}

		return api.NoMatch

	}

	// success
	return
}
