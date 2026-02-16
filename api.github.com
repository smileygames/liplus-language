{
  "openapi": "3.1.1",
  "info": {
    "title": "Li+ GitHub Unified I/O",
    "description": "Issue + PR + CI Polling (Org + Branch Ref Compatible)",
    "version": "3.2.0"
  },
  "servers": [
    { "url": "https://api.github.com" }
  ],
  "components": {
    "schemas": {},
    "securitySchemes": {
      "BearerAuth": {
        "type": "http",
        "scheme": "bearer"
      }
    }
  },
  "security": [
    { "BearerAuth": [] }
  ],
  "paths": {

    "/repos/Liplus-Project/liplus-language/issues": {
      "get": {
        "operationId": "listIssues",
        "x-openai-isConsequential": true
      },
      "post": {
        "operationId": "createIssue",
        "x-openai-isConsequential": true,
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "required": ["title"],
                "properties": {
                  "title": { "type": "string" },
                  "body": { "type": "string" },
                  "labels": {
                    "type": "array",
                    "items": { "type": "string" }
                  }
                }
              }
            }
          }
        }
      }
    },

    "/repos/Liplus-Project/liplus-language/issues/{issue_number}": {
      "get": {
        "operationId": "getIssue",
        "x-openai-isConsequential": true,
        "parameters": [
          {
            "name": "issue_number",
            "in": "path",
            "required": true,
            "schema": { "type": "integer" }
          }
        ]
      },
      "patch": {
        "operationId": "updateIssue",
        "x-openai-isConsequential": true,
        "parameters": [
          {
            "name": "issue_number",
            "in": "path",
            "required": true,
            "schema": { "type": "integer" }
          }
        ],
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "title": { "type": "string" },
                  "body": { "type": "string" },
                  "state": {
                    "type": "string",
                    "enum": ["open", "closed"]
                  },
                  "labels": {
                    "type": "array",
                    "items": { "type": "string" }
                  }
                }
              }
            }
          }
        }
      }
    },

    "/repos/Liplus-Project/liplus-language/issues/{issue_number}/comments": {
      "get": {
        "operationId": "listIssueComments",
        "x-openai-isConsequential": true,
        "parameters": [
          {
            "name": "issue_number",
            "in": "path",
            "required": true,
            "schema": { "type": "integer" }
          }
        ]
      },
      "post": {
        "operationId": "createIssueComment",
        "x-openai-isConsequential": true,
        "parameters": [
          {
            "name": "issue_number",
            "in": "path",
            "required": true,
            "schema": { "type": "integer" }
          }
        ],
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "required": ["body"],
                "properties": {
                  "body": { "type": "string" }
                }
              }
            }
          }
        }
      }
    },

    "/repos/Liplus-Project/liplus-language/contents/{path}": {
      "get": {
        "operationId": "getRepoContent",
        "x-openai-isConsequential": true,
        "parameters": [
          {
            "name": "path",
            "in": "path",
            "required": true,
            "schema": { "type": "string" }
          },
          {
            "name": "ref",
            "in": "query",
            "required": false,
            "schema": { "type": "string" }
          }
        ]
      },
      "put": {
        "operationId": "createOrUpdateRepoFile",
        "x-openai-isConsequential": true,
        "parameters": [
          {
            "name": "path",
            "in": "path",
            "required": true,
            "schema": { "type": "string" }
          }
        ],
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "required": ["message", "content"],
                "properties": {
                  "message": { "type": "string" },
                  "content": { "type": "string" },
                  "sha": { "type": "string" },
                  "branch": { "type": "string" }
                }
              }
            }
          }
        }
      }
    },

    "/repos/Liplus-Project/liplus-language/git/ref/{ref}": {
      "get": {
        "operationId": "getGitRef",
        "x-openai-isConsequential": true,
        "parameters": [
          {
            "name": "ref",
            "in": "path",
            "required": true,
            "schema": { "type": "string" }
          }
        ]
      }
    },

    "/repos/Liplus-Project/liplus-language/git/refs": {
      "post": {
        "operationId": "createGitRef",
        "x-openai-isConsequential": true,
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "required": ["ref", "sha"],
                "properties": {
                  "ref": { "type": "string" },
                  "sha": { "type": "string" }
                }
              }
            }
          }
        }
      }
    },

    "/repos/Liplus-Project/liplus-language/git/refs/{ref}": {
      "delete": {
        "operationId": "deleteGitRef",
        "x-openai-isConsequential": true,
        "parameters": [
          {
            "name": "ref",
            "in": "path",
            "required": true,
            "schema": { "type": "string" }
          }
        ]
      }
    },

    "/repos/Liplus-Project/liplus-language/pulls": {
      "get": {
        "operationId": "listPullRequests",
        "x-openai-isConsequential": true
      },
      "post": {
        "operationId": "createPullRequest",
        "x-openai-isConsequential": true,
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "required": ["title", "head", "base"],
                "properties": {
                  "title": { "type": "string" },
                  "body": { "type": "string" },
                  "head": { "type": "string" },
                  "base": { "type": "string" },
                  "draft": { "type": "boolean", "default": false }
                }
              }
            }
          }
        }
      }
    },

    "/repos/Liplus-Project/liplus-language/pulls/{pull_number}": {
      "get": {
        "operationId": "getPullRequest",
        "x-openai-isConsequential": true,
        "parameters": [
          {
            "name": "pull_number",
            "in": "path",
            "required": true,
            "schema": { "type": "integer" }
          }
        ]
      }
    },

    "/repos/Liplus-Project/liplus-language/pulls/{pull_number}/files": {
      "get": {
        "operationId": "listPullRequestFiles",
        "x-openai-isConsequential": true,
        "parameters": [
          {
            "name": "pull_number",
            "in": "path",
            "required": true,
            "schema": { "type": "integer" }
          }
        ]
      }
    },

    "/repos/Liplus-Project/liplus-language/pulls/{pull_number}/commits": {
      "get": {
        "operationId": "listPullRequestCommits",
        "x-openai-isConsequential": true,
        "parameters": [
          {
            "name": "pull_number",
            "in": "path",
            "required": true,
            "schema": { "type": "integer" }
          }
        ]
      }
    },

    "/repos/Liplus-Project/liplus-language/commits/{ref}/check-runs": {
      "get": {
        "operationId": "listCommitCheckRuns",
        "x-openai-isConsequential": true,
        "parameters": [
          {
            "name": "ref",
            "in": "path",
            "required": true,
            "schema": { "type": "string" }
          }
        ]
      }
    },

    "/repos/Liplus-Project/liplus-language/actions/workflows/liplus-ci.yml/runs": {
      "get": {
        "operationId": "listLiplusCiRuns",
        "x-openai-isConsequential": true
      }
    }
  }
}
