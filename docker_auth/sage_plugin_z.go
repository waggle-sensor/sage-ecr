package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/cesanta/docker_auth/auth_server/api"
)

// example api.AuthRequestInfo
// ------------
// Account: <username>
// Type: repository
// Name: test/alpine
// Service: Docker registry
// IP: 172.20.0.1
// Actions: pull,push
// Labels:
// ------------

var (
	ecrAuthZEndpoint string
	ecrAuthZToken    string

	DEBUG_MODE bool

	Authz SageAuthz
)

type AuthRequestInfo struct {
	Account string     `json:"account"`
	Type    string     `json:"type"`
	Name    string     `json:"name"`
	Service string     `json:"service"`
	IP      net.IP     `json:"ip"`
	Actions []string   `json:"actions"`
	Labels  api.Labels `json:"labels"`
}

func (ai AuthRequestInfo) String() string {
	return fmt.Sprintf("{%s %s %s %s}", ai.Account, strings.Join(ai.Actions, ","), ai.Type, ai.Name)
}

// NewAuthRequestInfo creates objetc that can be exported into JSON correctly
func NewAuthRequestInfo(ai *api.AuthRequestInfo) AuthRequestInfo {
	ai_new := AuthRequestInfo{}
	ai_new.Account = ai.Account
	ai_new.Type = ai.Type
	ai_new.Name = ai.Name
	ai_new.Service = ai.Service
	ai_new.IP = ai.IP
	ai_new.Actions = ai.Actions
	ai_new.Labels = ai.Labels
	return ai_new
}

func init() {
	ecrAuthZEndpoint = os.Getenv("ecrAuthZEndpoint")
	ecrAuthZToken = os.Getenv("ecrAuthZToken")

	DEBUG_MODE = os.Getenv("DEBUG_MODE") == "1"

	if ecrAuthZEndpoint == "" {
		log.Fatalf("Environment variable \"ecrAuthZEndpoint\" not defined")
		return
	}

	if ecrAuthZToken == "" {
		log.Fatalf("Environment variable \"ecrAuthZToken\" not defined")
		return
	}

	// if ecrAuthZUser == "" {
	// 	log.Fatalf("Environment variable \"ecrAuthZUser\" not defined")
	// 	return
	// }

	// if ecrAuthZPassword == "" {
	// 	log.Fatalf("Environment variable \"ecrAuthZPassword\" not defined")
	// 	return
	// }

}

// SageAuthz this implements the interface api.Authenticator from https://github.com/cesanta/docker_auth/blob/master/auth_server/api/authz.go
type SageAuthz struct {
}

//Authorize _
func (sa *SageAuthz) Authorize(ai *api.AuthRequestInfo) ([]string, error) {

	//ai_new := NewAuthRequestInfo(ai)

	return SageAuthorize(ai)

}

// Stop _
func (sa *SageAuthz) Stop() {
	return
}

// Name _
func (sa *SageAuthz) Name() string {
	return "SAGE Authorization"
}

// SageAuthorize _
func SageAuthorize(ai *api.AuthRequestInfo) (authorized_actions []string, err error) {

	aiNew := NewAuthRequestInfo(ai)

	var jsonData []byte
	jsonData, err = json.Marshal(aiNew)
	if err != nil {
		log.Println(err)
	}
	if DEBUG_MODE {
		fmt.Println(string(jsonData))
	}

	payload := strings.NewReader(string(jsonData))
	client := &http.Client{
		Timeout: time.Second * 5,
	}
	var req *http.Request
	req, err = http.NewRequest("POST", ecrAuthZEndpoint, payload)
	if err != nil {
		log.Print("NewRequest returned: " + err.Error())
		//http.Error(w, err.Error(), http.StatusInternalServerError)
		err = fmt.Errorf("NewRequest returned: %s", err.Error())
		return
	}

	//auth := ecrAuthZUser + ":" + ecrAuthZPassword
	//fmt.Printf("auth: %s\n", auth)
	//authEncoded := base64.StdEncoding.EncodeToString([]byte(auth))
	req.Header.Add("Authorization", "sage "+ecrAuthZToken)

	//req.Header.Add("Accept", "application/json; indent=4")
	//req.Header.Add("Content-Type", "application/x-www-form-urlencoded")

	var res *http.Response
	res, err = client.Do(req)
	if err != nil {
		log.Print(err)
		//http.Error(w, err.Error(), http.StatusInternalServerError)

		err = fmt.Errorf("client.Do returned: %s", err.Error())
		return
	}
	defer res.Body.Close()
	var body []byte
	body, err = ioutil.ReadAll(res.Body)
	if err != nil {
		//http.Error(w, err.Error(), http.StatusInternalServerError)

		err = fmt.Errorf("ioutil.ReadAll returned: %s", err.Error())
		return
	}

	//dat := TokenResponse{}
	//jsonErr := json.Unmarshal(body, &dat)

	//log.Printf("dat.Username: %s\n", dat.Username)

	if res.StatusCode == 403 { // "Forbidden", not a 401 !
		err = api.NoMatch
		return
	}

	if res.StatusCode != 200 {
		fmt.Printf("request was denied: %s", body)
		//http.Error(w, fmt.Sprintf("token introspection failed (%d) (%s)", res.StatusCode, body), http.StatusInternalServerError)

		err = fmt.Errorf("authorization failed (%d) (%s)", res.StatusCode, body)
		return
	}

	log.Printf("looks good: %s\n", string(body))

	authorized_actions = strings.Split(string(body), ",")

	return
}
