# Context Builder

Context Builder selects what AMADEUS should remember or inspect before a chat response.

It keeps prompt-context logic outside Core and Chat:

- Core routes.
- Context Builder selects context.
- Chat formats the final prompt.
- Storage stores history.
- Project File Reader reads approved project docs.
