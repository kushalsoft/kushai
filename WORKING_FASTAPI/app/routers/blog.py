from typing import Annotated, Any, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy import UUID

from app.models.user import User
from app.models.blog import Blog
from app.models.post import Post

from app.schemas.blog import Blog as BlogSchema, BlogCreate, BlogDetails, BlogsList
from app.schemas.post import PostsList

from app.core.exceptions import AuthFailedException, BadRequestException, ForbiddenException, NotFoundException
from app.core.database import DBSessionDep
from app.core.jwt import (
    mail_token,
    create_token_pair,
    refresh_token_state,
    decode_access_token,
    add_refresh_token_cookie,
    oauth2_scheme,
    SUB, JTI, EXP,
)

router = APIRouter()
#     prefix="/api/blog",
#     tags=["blogs"],
#     responses={404: {"description": "Not found"}},
# )

@router.get("/", response_model=BlogsList)
async def blog_list(
    #token: Annotated[str, Depends(oauth2_scheme)],
    token: str,
    db: DBSessionDep,
):
    payload = await decode_access_token(token=token, db=db)
    user = await User.find_by_username(db=db, username=payload[SUB])
    if not user:
        raise NotFoundException(detail="User not found")
    username = user.username
    blogs = await Blog.find_all_by_username(db=db, username=username)
    return BlogsList(blogs=blogs)

@router.post("/{id}", response_model=BlogDetails)
async def blog_details(
    token: str,
    db: DBSessionDep,
    id: str = Path(..., title="The ID of the blog to delete"),
):
    payload = await decode_access_token(token=token, db=db)
    user = await User.find_by_username(db=db, username=payload[SUB])

    if not user:
        raise AuthFailedException()
    # Check if the provided ID is a valid UUID
    try:
        uuid_obj = uuid.UUID(id)
    except ValueError:
        raise BadRequestException
    
    blog = await Blog.find_by_id(db=db, id=id)
    if blog is None:
        raise NotFoundException()
    if blog.created_by != user.id:
        raise AuthFailedException()
    
    titles = await Post.find_all_titles_by_blog(db=db, blog_id=blog.id)

    blog_schema = BlogSchema.model_validate(blog.__dict__)
    blog_details = BlogDetails(blog=blog_schema, post_titles=titles)
    return blog_details

@router.post("/create/", response_model=BlogSchema)
async def create_blog(
    token: str,
    db: DBSessionDep,
    data: BlogCreate
):
    payload = await decode_access_token(token=token, db=db)
    user = await User.find_by_username(db=db, username=payload[SUB])
    if not user:
        raise AuthFailedException()
    
    # Check if the blog title is available for the user
    if not await Blog.check_availability(db=db, created_by=user.id, title=data.title):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Blog title already exists for the user")

    blog_data = data.model_dump()
    blog_data["created_by"] = user.id
    blog = Blog(**blog_data)

    blog = await blog.create(db=db, **blog_data)
    blog_schema = BlogSchema.model_validate(blog.__dict__)
    return blog_schema

@router.delete("/delete/{id}", response_model=None)
async def delete_blog(
    #token: Annotated[str, Depends(oauth2_scheme)],
    token: str,
    db: DBSessionDep,
    id: str = Path(..., title="The ID of the blog to delete"),
):
    payload = await decode_access_token(token=token, db=db)
    user = await User.find_by_username(db=db, username=payload[SUB])
    if not user:
        raise AuthFailedException()

    # Delete the blog by its ID
    deleted_blog = await Blog.delete(db=db, id=id)
    if not deleted_blog:
        raise NotFoundException(detail="Blog not found")

    return {"message": "Blog deleted successfully"}