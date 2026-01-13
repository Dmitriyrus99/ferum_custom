from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from frappeclient import FrappeClient
from passlib.context import CryptContext

from ..auth import (  # Keep create_access_token and get_current_user from auth.py
	create_access_token,
	get_current_user,
)
from ..config import settings

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Initialize FrappeClient for authentication
frappe_client = FrappeClient(settings.ERP_API_URL, settings.ERP_API_KEY, settings.ERP_API_SECRET)


class UserInDB:
	def __init__(
		self,
		username: str,
		hashed_password: str,
		roles: list[str],
		twofa_enabled: bool = False,
	):
		self.username = username
		self.hashed_password = hashed_password
		self.roles = roles
		self.twofa_enabled = twofa_enabled


def verify_password(plain_password, hashed_password):
	return pwd_context.verify(plain_password, hashed_password)


# Placeholder for ERPNext user authentication
def authenticate_user(username: str, password: str):
	# In a real application, you would query ERPNext to verify username and password.
	# This is a mock authentication for demonstration.
	# You would typically use frappe_client.authenticate(username, password) or similar.
	# For now, let's mock a user.
	if username == "admin" and password == "admin":  # Replace with actual ERPNext authentication
		return UserInDB(
			username="admin",
			hashed_password=pwd_context.hash("admin"),
			roles=["Administrator"],
			twofa_enabled=True,
		)
	if username == "pm" and password == "pm":
		return UserInDB(
			username="pm",
			hashed_password=pwd_context.hash("pm"),
			roles=["Project Manager"],
			twofa_enabled=False,
		)
	return None


@router.post("/token")
async def login_for_access_token(
	form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
):
	user = authenticate_user(form_data.username, form_data.password)
	if not user:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Incorrect username or password",
			headers={"WWW-Authenticate": "Bearer"},
		)

	# 2FA Check
	if user.twofa_enabled:
		# In a real scenario, you would generate an OTP and send it to the user (email/app)
		# and then expect the OTP in the /token/2fa endpoint.
		# For this placeholder, we'll just raise an error if 2FA is enabled.
		raise HTTPException(
			status_code=status.HTTP_403_FORBIDDEN,
			detail="Two-factor authentication required. Please call /token/2fa with OTP.",
		)

	access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
	access_token = create_access_token(
		data={"sub": user.username, "roles": user.roles},
		expires_delta=access_token_expires,
	)
	return {"access_token": access_token, "token_type": "bearer"}


@router.post("/token/2fa")
async def verify_2fa_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], otp: str):
	# This is a placeholder for 2FA verification.
	# In a real scenario, you would verify the OTP against the user's stored 2FA secret
	# or an external 2FA service.
	user = authenticate_user(form_data.username, form_data.password)  # Re-authenticate user
	if not user or not user.twofa_enabled:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Invalid credentials or 2FA not enabled.",
		)

	if otp == "123456":  # Mock OTP for demonstration
		access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
		access_token = create_access_token(
			data={"sub": user.username, "roles": user.roles},
			expires_delta=access_token_expires,
		)
		return {"access_token": access_token, "token_type": "bearer"}
	else:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid OTP.")


@router.get("/users/me")
async def read_users_me(current_user: Annotated[str, Depends(get_current_user)]):
	return {"username": current_user}
