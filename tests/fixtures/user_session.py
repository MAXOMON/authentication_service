from base64 import b64encode

from httpx import AsyncClient, Response



class UserSession:
    def __init__(self, client: AsyncClient):
        self.client: AsyncClient = client
        self.access_token = None
        self.refresh_token = None
        self.device_id = None


    @staticmethod
    def get_encoded_credentials(username: str, password: str):
        credentials = f"{username}:{password}"
        return b64encode(credentials.encode()).decode()

    def user_init(self, username: str, password: str, device_id: str) -> bytes:
        self.encoded = self.get_encoded_credentials(username, password)
        self.__user_email = username
        self.__user_password = password
        self.device_id = device_id

    @property
    def user_email(self):
        return self.__user_email

    @user_email.setter
    def user_email(self, value):
        self.__user_email = value
        self.encoded = self.get_encoded_credentials(value, self.__user_password)

    @property
    def user_password(self):
        return self.__user_password

    @user_password.setter
    def user_password(self, value):
        self.__user_password = value
        self.encoded = self.get_encoded_credentials(self.__user_email, value)

    async def register(self):
        response: Response = await self.client.post(
            url="/auth/register",
            headers={"Authorization": f"Basic {self.encoded}"},
            cookies={"device_id": self.device_id}
        )
        return response
    
    async def login(self):
        response: Response = await self.client.post(
            url="/auth/login",
            headers={"Authorization": f"Basic {self.encoded}"},
            cookies={"device_id": self.device_id}
        )
        self.access_token = response.cookies.get("access_token")
        self.refresh_token = response.cookies.get("refresh_token")
        return response

    async def refresh(self):
        response: Response = await self.client.post(
            url="/auth/refresh",
            headers={"Authorization": f"Bearer {self.refresh_token}"},
            cookies={"device_id": self.device_id}
        )
        self.access_token = response.cookies.get("access_token")
        self.refresh_token = response.cookies.get("refresh_token")
        return response

    async def logout(self):
        response: Response = await self.client.post(
            url="/auth/user/logout",
            headers={"Authorization": f"Bearer {self.access_token}"},
            cookies={"device_id": self.device_id}
        )
        self.access_token = None
        self.refresh_token = None
        return response

    async def close_all_sessions(self):
        response: Response = await self.client.post(
            url="/auth/user/close_all_sessions",
            headers={"Authorization": f"Bearer {self.access_token}"},
            cookies={"device_id": self.device_id}
        )
        self.access_token = None
        self.refresh_token = None
        return response

    async def change_email(self, new_email: str):
        response: Response = await self.client.post(
            url="/auth/user/change_email",
            json={"email": new_email, "password": self.__user_password},
            headers={"Authorization": f"Bearer {self.access_token}"},
            cookies={"device_id": self.device_id}
        )
        if response.status_code == 200:
            self.user_email = new_email
        return response
    
    async def change_password(self, new_password: str):
        response: Response = await self.client.post(
            url="/auth/user/change_password",
            json={"new_password": new_password, "password": self.__user_password},
            headers={"Authorization": f"Bearer {self.access_token}"},
            cookies={"device_id": self.device_id}
        )
        if response.status_code == 200:
            self.user_password = new_password
        return response

    async def get_profile(self):
        response: Response = await self.client.request(
            method="GET",
            url="/auth/user/profile",
            json={"password": self.__user_password},
            headers={"Authorization": f"Bearer {self.access_token}"},
            cookies={"device_id": self.device_id}
        )
        return response

    async def delete_profile(self):
        response: Response = await self.client.request(
            method="DELETE",
            url="/auth/user/profile",
            json={"email": self.__user_email, "password": self.__user_password},
            headers={"Authorization": f"Bearer {self.access_token}"},
            cookies={"device_id": self.device_id}
        )
        return response
    